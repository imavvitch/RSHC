from pathlib import Path
import json,math,struct
out=Path(__file__).resolve().parent;out.mkdir(exist_ok=True)
positions=[];normals=[];uv=[];joints=[];weights=[];wide=[];tall=[];indices=[];lower_indices=[];upper_indices=[]
rings=[(0,.20),(.2,.23),(.4,.16),(.6,.25),(.8,.24),(1,.14)];segments=16
for y,width in rings:
 for i in range(segments):
  t=i*2*math.pi/segments;x=width*math.cos(t);z=.12*math.sin(t)
  positions.append((x,y,z));n=(math.cos(t)/width,0,math.sin(t)/.12);length=math.sqrt(sum(v*v for v in n));normals.append(tuple(v/length for v in n))
  uv.append((i/segments,y));joints.append((0,1,0,0));w=min(1,max(0,(y-.2)/.6));weights.append((1-w,w,0,0))
  influence=max(0,1-abs(y-.4)/.35);wide.append((x*.8*influence,0,0));tall.append((0,y*.4,0))
for r in range(len(rings)-1):
 for i in range(segments):
  a=r*segments+i;b=r*segments+(i+1)%segments;c=a+segments;d=b+segments
  face=(a,c,b,b,c,d);indices.extend(face);(lower_indices if r<2 else upper_indices).extend(face)
for y,base,reverse in [(0,0,False),(1,(len(rings)-1)*segments,True)]:
 center=len(positions);positions.append((0,y,0));normals.append((0,1 if reverse else -1,0));uv.append((.5,.5));joints.append((0,1,0,0));weights.append((0,1,0,0)if reverse else(1,0,0,0));wide.append((0,0,0));tall.append((0,y*.4,0))
 for i in range(segments):
  a=base+i;b=base+(i+1)%segments;face=(center,b,a)if reverse else(center,a,b);indices.extend(face);(upper_indices if reverse else lower_indices).extend(face)
blob=bytearray();views=[];accessors=[]
def accessor(values,kind,component=5126,target=None,bounds=False):
 dims={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[kind];fmt={5126:'f',5123:'H'}[component]
 while len(blob)%4:blob.append(0)
 offset=len(blob);flat=[v for row in values for v in(row if isinstance(row,(tuple,list))else(row,))];blob.extend(struct.pack('<'+fmt*len(flat),*flat))
 view={'buffer':0,'byteOffset':offset,'byteLength':len(blob)-offset}
 if target:view['target']=target
 views.append(view);a={'bufferView':len(views)-1,'componentType':component,'count':len(values),'type':kind}
 if bounds:
  rows=[row if isinstance(row,(tuple,list))else(row,)for row in values];a['min']=[min(row[i]for row in rows)for i in range(dims)];a['max']=[max(row[i]for row in rows)for i in range(dims)]
 accessors.append(a);return len(accessors)-1
attrs={'POSITION':accessor(positions,'VEC3',target=34962,bounds=True),'NORMAL':accessor(normals,'VEC3',target=34962),'TEXCOORD_0':accessor(uv,'VEC2',target=34962),'JOINTS_0':accessor(joints,'VEC4',5123,34962),'WEIGHTS_0':accessor(weights,'VEC4',target=34962)}
idx_lower=accessor(lower_indices,'SCALAR',5123,34963,bounds=True)
idx_upper=accessor(upper_indices,'SCALAR',5123,34963,bounds=True)
targets=[{'POSITION':accessor(wide,'VEC3',target=34962,bounds=True)},{'POSITION':accessor(tall,'VEC3',target=34962,bounds=True)}]
identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];upper=identity.copy();upper[13]=-.5
ibm=accessor([identity,upper],'MAT4')
doc={'asset':{'version':'2.0','generator':'RSHC morph practice generator'},'scene':0,'scenes':[{'nodes':[0,2]}],
 'nodes':[{'name':'DemoRoot','children':[1]},{'name':'DemoSpine','translation':[0,.5,0]},{'name':'SK_SectionDemo','mesh':0,'skin':0}],
 'skins':[{'name':'DemoSkeleton','inverseBindMatrices':ibm,'skeleton':0,'joints':[0,1]}],
 'meshes':[{'name':'SK_SectionDemo','weights':[0,0],'extras':{'targetNames':['WaistWide','BodyTall']},'primitives':[{'attributes':attrs,'indices':idx_lower,'material':0,'targets':targets},{'attributes':attrs,'indices':idx_upper,'material':1,'targets':targets}]}],
 'materials':[{'name':'RSHC_tint_lower','pbrMetallicRoughness':{'baseColorFactor':[1,.35,.04,1],'metallicFactor':0,'roughnessFactor':.65}},{'name':'RSHC_tint_upper','pbrMetallicRoughness':{'baseColorFactor':[.04,.35,1,1],'metallicFactor':0,'roughnessFactor':.65}}],
 'buffers':[{'byteLength':len(blob)}],'bufferViews':views,'accessors':accessors}
j=json.dumps(doc,separators=(',',':')).encode();j+=b' '*((-len(j))%4);blob+=b'\0'*((-len(blob))%4)
glb=struct.pack('<4sII',b'glTF',2,12+8+len(j)+8+len(blob))+struct.pack('<II',len(j),0x4E4F534A)+j+struct.pack('<II',len(blob),0x004E4942)+blob
path=out/'SK_SectionDemo.glb';path.write_bytes(glb)
assert struct.unpack_from('<I',glb,8)[0]==len(glb)
assert len(positions)==len(wide)==len(tall)==len(weights)and max(indices)<len(positions)
assert all(abs(sum(w)-1)<1e-6 for w in weights)
assert any(abs(v[0])>.01 for v in wide)and max(v[1]for v in tall)>.3
(out/'MODEL-INFO.json').write_text(json.dumps({'file':path.name,'vertices':len(positions),'triangles':len(indices)//3,'bones':['DemoRoot','DemoSpine'],'morphs':['WaistWide','BodyTall'],'sections':['lower','upper'],'units':'metres','purpose':'skeletal test attachment; not a native body replacement'},indent=2))
print(f'Created {path}: {len(glb)} bytes, two bones, two named morphs')
