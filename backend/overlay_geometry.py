"""Complete caption rows and nearby persistent bright/colored symbols, in source pixels."""
import numpy as np


def join_rows(lines):
    # Split malformed OCR lines into separate baselines before grouping words.
    words=[tuple(word) for line in lines for word in line if 8<=word[3]<=76 and 2<=word[2]<=640]
    rows=[]
    for x,y,w,h in sorted(set(words),key=lambda r:(r[1]+r[3]/2,r[0])):
        pending=(x,y,x+w,y+h)
        match=None
        for i,(a,b,c,d) in enumerate(rows):
            low=min(h,d-b);high=max(h,d-b)
            if high>low*1.6 or abs((y+h/2)-(b+d)/2)>low*.3:continue
            if min(y+h,d)-max(y,b)<low*.65:continue
            if max(0,a-(x+w),x-c)>high*1.3:continue
            match=i;break
        if match is None:rows.append(pending)
        else:
            a,b,c,d=rows[match];rows[match]=(min(a,x),min(b,y),max(c,x+w),max(d,y+h))
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
    # A text row stays a text row. Emoji never increase its height or union
    # separate rows into the large horizontal bands seen in legacy projects.
    x,y,right,bottom=row;line_h=bottom-y
    px=min(8,max(4,line_h*.12));py=min(6,max(3,line_h*.1))
    return {'x':max(bounds[0],(x-px)/720),'y':max(bounds[1],(y-py)/1280),
            'right':min(bounds[2],(right+px)/720),'bottom':min(bounds[3],(bottom+py)/1280),
            'method':'blur','kind':'text'}


def caption_boxes(row,symbols,bounds):
    result=[complete_caption(row,[],bounds)]
    x,y,right,bottom=row;h=bottom-y
    for a,b,c,d in sorted(symbols,key=lambda box:box[0]):
        if len(result)>=3:break
        if not .6*h<=d-b<=1.8*h or not .7<=(c-a)/(d-b)<=1.4:continue
        if min(bottom,d)-max(y,b)<min(h,d-b)*.6:continue
        if max(0,a-right,x-c)>h*1.8 or a<row[0]-h*2 or c>row[2]+h*6:continue
        if a>=x and c<=right:continue
        result.append({'x':max(bounds[0],(a-4)/720),'y':max(bounds[1],(b-4)/1280),
                       'right':min(bounds[2],(c+4)/720),'bottom':min(bounds[3],(d+4)/1280),
                       'method':'blur','kind':'emoji'})
        x=min(x,a);right=max(right,c)
    return result
