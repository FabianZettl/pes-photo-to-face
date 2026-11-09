-- Test of faceai.lua's release from fl26regen's list against a fake process (see tests/check_release.py)
-- a fake process: appearance table (as in test5) + a fake fl26regen.dll image holding a pointer to g_nlist on the "heap"
local FACEAI, WORKDIR = arg[1], arg[2]
local function u32_(v) return string.char(v%256,math.floor(v/256)%256,math.floor(v/65536)%256,math.floor(v/16777216)%256) end
local rec={} for i=0,199 do rec[#rec+1]=u32_(100000+i*3)..string.rep("\0",68) end   -- a synthetic appearance table: 200 records
local d=table.concat(rec)
local APP=0x100000; local TBL=APP+0x50910; local CNT=APP+0x4c7252; local count=#d/72
local DLLBASE, DLLSIZE, HEAP = 0x7ff600000000, 0x40000, 0x7ff700010000
local function u32(v) return string.char(v%256,math.floor(v/256)%256,math.floor(v/65536)%256,math.floor(v/16777216)%256) end
local function u64(v) return u32(v%4294967296)..u32(math.floor(v/4294967296)) end
-- list: 3000 entries ids 190000.., face index = id%100, the managed ids among them; keep=0
local list={} for i=0,2999 do local id=190000+i*2; list[#list+1]=u32(id)..string.char((id%100)%256,0,0,0) end
local listmem=table.concat(list)..string.rep("\0",8*65536-#table.concat(list))   -- a calloc(65536*8) like the DLL
local image=string.rep("\0",DLLSIZE)
local function put(s,off,str) return s:sub(1,off)..str..s:sub(off+#str+1) end
image=put(image,0x3C,u32(0x80))                      -- e_lfanew
image=put(image,0x80+0x50,u32(DLLSIZE))              -- SizeOfImage
image=put(image,0x20000,u64(DLLBASE+0x500))          -- a pointer into the image itself (must be skipped)
image=put(image,0x20010,u64(0x7ff800000000))         -- a pointer to nothing readable
image=put(image,0x20020,u64(HEAP))                   -- g_nlist
local regions={ {DLLBASE,image}, {HEAP,listmem} }
local function find(a,n) for _,r in ipairs(regions) do local o=a-r[1]; if o>=0 and o+n<=#r[2] then return r,o end end end
memory={get_process_info=function() return {base=0} end,
 unpack=function(t,s) local v=0; for i=#s,1,-1 do v=v*256+s:byte(i) end return v end,
 pack=function(t,v) return u32(v) end,
 read=function(a,n)
   if a==0x3705E10 then return string.char(0,0,0x20,0,0,0,0,0) end
   if a==0x200000+0x60 then return string.char(0,0,0x10,0,0,0,0,0) end
   if a==CNT then return string.char(count%256,math.floor(count/256)) end
   if a>=TBL and a<TBL+#d+72*50 then local o=a-TBL; return d:sub(o+1,o+n) end
   local r,o=find(a,n); if not r then error("unreadable") end return r[2]:sub(o+1,o+n) end,
 write=function(a,s)
   if a==CNT then count=s:byte(1)+256*s:byte(2) return end
   if a>=TBL and a<TBL+#d+72*50 then local o=a-TBL; d=d:sub(1,o)..s..d:sub(o+#s+1) return end
   local r,o=find(a,#s); if not r then error("write to unmapped") end r[2]=r[2]:sub(1,o)..s..r[2]:sub(o+#s+1) end}
local logs={} log=function(s) logs[#logs+1]=s end
local clock=0 os.clock=function() return clock end
local m=dofile(FACEAI)
local released_calls=0
m.dll_open=function()
  return {base=DLLBASE,size=DLLSIZE,face=function(id)   -- like fl26_regen_face: the portrait key, -1 when released
    local o=(id-190000)/2*8; local r=regions[2][2]; if o<0 or o>=#r or o~=math.floor(o) then return -1 end
    local face=memory.unpack("u16",r:sub(o+5,o+6)); if face==0xFFFF then return -1 end return face+1000 end}
end
local function face_of(id) local r=regions[2][2]; local o=(id-190000)/2*8; return memory.unpack("u16",r:sub(o+5,o+6)) end
m.init({register=function() end, sider_dir=WORKDIR})
local mi=io.open(WORKDIR.."content/faceai/faceai.csv","w"); mi:write("Id,NoseHeight\r\n190010,3\r\n190012,2\r\n189999,1\r\n"); mi:close()
clock=clock+40; m.tick()

assert(face_of(190010)==65535 and face_of(190012)==65535, "managed players must be released (face = -1)")
assert(face_of(190014)==14, "an unmanaged player must be left alone")
assert(m.rewrite({}, "common\\render\\symbol\\player\\190010.dds"):find("regen\\1010.dds",1,true), "portrait redirect")
assert(m.rewrite({}, "common\\x\\y.dds")==nil)
io.write("release ok\n")
-- the DLL "rebuilds its list" (database block moved): faces come back, the next tick takes them over again
local r=regions[2]; r[2]=put(r[2],(190010-190000)/2*8+4,string.char(10,0)); r[2]=put(r[2],(190012-190000)/2*8+4,string.char(12,0))
clock=clock+4; m.tick()
assert(face_of(190010)==65535 and face_of(190012)==65535, "released again after the DLL rebuilt its list")
io.write("re-release ok\n")
