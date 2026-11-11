"""Complete caption rows and nearby persistent bright/colored symbols, in source pixels."""
import numpy as np


def join_rows(lines):
    rows=[]
    for words in lines:
        x=min(p[0] for p in words);y=min(p[1] for p in words)
        right=max(p[0]+p[2] for p in words);bottom=max(p[1]+p[3] for p in words)
        pending=(x,y,right,bottom)
        while True:
            match=None
            for i,other in enumerate(rows):
                a,b,c,d=pending;e,f,g,h=other
                height=min(d-b,h-f)
                vertical=min(d,h)-max(b,f)
                gap=max(0,e-c,a-g)
                if vertical>=height*.5 and gap<=max(d-b,h-f)*2.1:
                    match=i;break
            if match is None:break
            other=rows.pop(match)
            pending=(min(pending[0],other[0]),min(pending[1],other[1]),max(pending[2],other[2]),max(pending[3],other[3]))
        rows.append(pending)
    return rows


def colored_symbols(image,bounds):
    """Candidates only. Adjacent geometry + temporal agreement confirm overlays."""
    rgb=np.asarray(image.convert('RGB').resize((360,640))).astype(np.int16)
    mask=(rgb.max(axis=2)>160)&((rgb.max(axis=2)-rgb.min(axis=2)>75)|(rgb.min(axis=2)>205))
    mask[:int(bounds[1]*640)]=False;mask[int(bounds[3]*640):]=False
    mask[:,:int(bounds[0]*360)]=False;mask[:,int(bounds[2]*360):]=False
    seen=np.zeros(mask.shape,dtype=bool);result=[]
    for y,x in zip(*np.where(mask)):
        if seen[y,x]:continue
        todo=[(int(y),int(x))];seen[y,x]=True
        left=right=int(x);top=bottom=int(y);count=0
        while todo:
            yy,xx=todo.pop();count+=1
            left=min(left,xx);right=max(right,xx);top=min(top,yy);bottom=max(bottom,yy)
            for a,b in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
                if 0<=a<640 and 0<=b<360 and mask[a,b] and not seen[a,b]:
                    seen[a,b]=True;todo.append((a,b))
        w,h=right-left+1,bottom-top+1
        if 7<=h<=110 and .35<=w/h<=2.3 and count>=max(20,w*h*.28):
            result.append((left*2,top*2,(right+1)*2,(bottom+1)*2))
    return sorted(result,key=lambda b:(b[2]-b[0])*(b[3]-b[1]),reverse=True)[:96]


def persistent_symbols(groups):
    result=[]
    for group in groups:
        for box in group:
            a,b,c,d=box;area=(c-a)*(d-b)
            found=0
            for other_group in groups:
                if any(max(0,min(c,g)-max(a,e))*max(0,min(d,h)-max(b,f))>=.65*max(area,(g-e)*(h-f))
                       for e,f,g,h in other_group):found+=1
            if found>=2 and box not in result:result.append(box)
    return result


def complete_caption(row,symbols,bounds):
    x,y,right,bottom=row;line_h=bottom-y
    # Include adjacent emoji and colored punctuation, but stop before unrelated
    # objects or a chain extending more than six letter heights past the row.
    changed=True
    while changed:
        changed=False
        for a,b,c,d in symbols:
            if not .4*line_h<=d-b<=2.2*line_h:continue
            if min(bottom,d)-max(y,b)<min(bottom-y,d-b)*.35:continue
            if max(0,a-right,x-c)>line_h*1.8:continue
            if a<row[0]-line_h*6 or c>row[2]+line_h*6:continue
            expanded=(min(x,a),min(y,b),max(right,c),max(bottom,d))
            if expanded!=(x,y,right,bottom):x,y,right,bottom=expanded;changed=True
    pad_x=max(12,line_h*.32);pad_y=max(10,line_h*.25)
    return {'x':max(bounds[0],(x-pad_x)/720),'y':max(bounds[1],(y-pad_y)/1280),
            'right':min(bounds[2],(right+pad_x)/720),'bottom':min(bounds[3],(bottom+pad_y)/1280),
            'method':'blur','kind':'text'}
