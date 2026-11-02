"""Independent optional calibration oracle. No capture hardware is accessed."""
import numpy as np
def decode(words):
    words=np.asarray(words,dtype=np.uint32);p=np.empty(4096,np.uint32);p[::2]=words&65535;p[1::2]=words>>16;p=p.reshape(64,64)
    r=p>>11;g=(p>>5)&63;b=p&31
    return np.stack([(r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)],2).astype(np.int32)
def gray(rgb):return (rgb[:,:,0]+2*rgb[:,:,1]+rgb[:,:,2])//4
class Calibration:
    def reset(self):
        self.bg=np.zeros((64,64),np.uint8);self.bg_count=0;self.noise=0;self.threshold=6
        self.prototypes=np.zeros((10,4,192),np.uint8);self.counts=np.zeros(10,np.uint8);self.limits=np.full(10,14,np.uint8)
        self.canonical=np.zeros((64,64),np.uint8);self.features=np.zeros(192,np.uint8)
    def __init__(self):self.reset()
    def metrics(self):return dict(foreground_count=0,mean_rgb=0,threshold=self.threshold,best_distance=65535,margin=0,reason=0)
    def valid_mask(self):return sum((1<<i) for i in range(10) if self.counts[i]==4)
    def restart_class(self,label):
        if 0<=label<10:self.counts[label]=0;self.limits[label]=14
    def capture_background(self,n,words):
        if n==0:self.reset()
        if n!=self.bg_count or n>=3:return -2
        current=gray(decode(words))
        if n:
            delta=current-self.bg.astype(np.int32);offset=int(np.partition(delta.ravel(),2047)[2047]);current=(current-offset).clip(0,255)
        if n:self.noise+=int(np.abs(current-self.bg.astype(np.int32)).sum())
        self.bg=((self.bg.astype(np.int32)*n+current)//(n+1)).astype(np.uint8);self.bg_count+=1
        noise=self.noise//(4096*(self.bg_count-1)) if self.bg_count>1 else 0;self.threshold=min(20,max(6,3*noise+4));return 0
    def extract(self,words):
        m=self.metrics()
        if self.bg_count!=3:m['reason']=1;return -2,m
        rgb=decode(words);current=gray(rgb);delta=current-self.bg.astype(np.int32)
        hist=np.bincount((delta+255).ravel(),minlength=512);offset=int(np.flatnonzero(np.cumsum(hist)>=2048)[0])-255
        mask=np.abs(delta-offset)>self.threshold
        padded=np.pad(mask.astype(np.uint8),1);neighbors=np.zeros((64,64),np.uint8)
        for dy in range(3):
            for dx in range(3):
                if (dy,dx)!=(1,1):neighbors+=padded[dy:dy+64,dx:dx+64]
        clean=mask&(neighbors>=2)
        # Independent flood fill; C uses a bounded label/union table.
        visited=np.zeros_like(clean);components=[]
        for y in range(64):
            for x in range(64):
                if not clean[y,x] or visited[y,x]:continue
                stack=[(y,x)];visited[y,x]=True;component=[]
                while stack:
                    yy,xx=stack.pop();component.append((yy,xx))
                    for dy in [-1,0,1]:
                        for dx in [-1,0,1]:
                            ny,nx=yy+dy,xx+dx
                            if 0<=ny<64 and 0<=nx<64 and clean[ny,nx] and not visited[ny,nx]:visited[ny,nx]=True;stack.append((ny,nx))
                components.append(component)
        clean=np.zeros_like(clean)
        if components:
            best=max(components,key=len)
            for y,x in best:clean[y,x]=True
        count=int(clean.sum());mean=rgb.reshape(-1,3).sum(0)//4096
        m.update(foreground_count=count,mean_rgb=(int(mean[0])<<16)|(int(mean[1])<<8)|int(mean[2]))
        if count<24:m['reason']=2;return -1,m
        ys,xs=np.nonzero(clean);minx,maxx=int(xs.min()),int(xs.max());miny,maxy=int(ys.min()),int(ys.max())
        if count>3600 or maxx-minx+1<6 or maxy-miny+1<6:m['reason']=3;return -2,m
        vals=np.sort(current[clean]);lo=int(vals[count//20]);hi=int(vals[count*19//20]);side=max(maxx-minx+1,maxy-miny+1);side+=(side+7)//8
        left=(minx+maxx+1-side)//2;top=(miny+maxy+1-side)//2
        self.canonical=np.zeros((64,64),np.uint8)
        for y in range(64):
            for x in range(64):
                sx=left+((2*x+1)*side)//128;sy=top+((2*y+1)*side)//128
                if 0<=sx<64 and 0<=sy<64 and clean[sy,sx]:self.canonical[y,x]=160 if hi-lo<8 else 63+(int(np.clip(current[sy,sx],lo,hi))-lo)*192//(hi-lo)
        can=self.canonical.astype(np.int32);hist=np.zeros((16,4),np.int64)
        for y in range(1,63):
            for x in range(1,63):
                dx=int(can[y,x+1]-can[y,x-1]);dy=int(can[y+1,x]-can[y-1,x]);ax,ay=abs(dx),abs(dy)
                if ax>2*ay:direction=0 if dx>=0 else 4
                elif ay>2*ax:direction=2 if dy>=0 else 6
                elif dx>=0:direction=1 if dy>=0 else 7
                else:direction=3 if dy>=0 else 5
                hist[(y//16)*4+x//16,direction&3]+=ax+ay
        f=np.zeros(192,np.uint8)
        for i in range(16):
            total=int(hist[i].sum())
            if total:f[i*4:i*4+4]=(hist[i]*255//total).astype(np.uint8)
        for gy in range(8):
            for gx in range(8):
                i=gy*8+gx;block=can[gy*8:gy*8+8,gx*8:gx*8+8]
                f[64+i]=int(block.sum())//64;f[128+i]=int((block!=0).sum())*255//64
        self.features=f;return 0,m
    @staticmethod
    def distance(a,b):
        def view(x):
            delta=np.abs(x.astype(np.int32)-b.astype(np.int32))
            return (int(delta[:64].sum())+int(delta[64:128].sum())//2+2*int(delta[128:].sum()))//224
        mirrored=np.concatenate([a[:64].reshape(4,4,4)[:,::-1,:][:,:,[0,3,2,1]].ravel(),a[64:128].reshape(8,8)[:,::-1].ravel(),a[128:].reshape(8,8)[:,::-1].ravel()])
        return min(view(a),view(mirrored))
    def capture_template(self,label,n,words):
        m=self.metrics()
        if not 0<=label<10 or not 0<=n<4 or self.counts[label]!=n:m['reason']=5;return -2,m
        result,m=self.extract(words)
        if result:return result,m
        self.prototypes[label,n]=self.features;self.counts[label]+=1
        if self.counts[label]==4:
            maximum=max(self.distance(self.prototypes[label,i],self.prototypes[label,j]) for i in range(4) for j in range(i+1,4))
            self.limits[label]=min(40,max(14,2*maximum+8))
        return 0,m
    def predict(self,words):
        result,m=self.extract(words)
        if result:return result,m
        if self.valid_mask()!=1023:m['reason']=4;return -2,m
        ds=[min(self.distance(self.features,p) for p in self.prototypes[k]) for k in range(10)]
        best=min(range(10),key=lambda k:ds[k]);second=min(ds[k] for k in range(10) if k!=best);m.update(best_distance=ds[best],margin=second-ds[best])
        if ds[best]>self.limits[best]:m['reason']=6;return -2,m
        if second-ds[best]<max(2,ds[best]//8):m['reason']=7;return -2,m
        return best,m
