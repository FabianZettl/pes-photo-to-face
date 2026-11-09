-- faceai_probe: READ-ONLY. F8 writes the in-memory PlayerAppearance table to content\faceai\appearance_mem_NN.bin (numbered per press)
-- (72 bytes per record) so the slider bit layout can be worked out offline. Changes nothing in the game.
-- Chain from fl26appcap.lua: obj = [exe+0x3705e10]; app = [obj+0x60]; table = app+0x50910;
-- u16 record count at app+0x4c7252 (with fl26appcap) or app+0x260552 (without).
local m = {}
local META = "content\\ml-immersion\\bridge\\players_dump.meta"
local BLOCK = 0x17C
local OUT = "content\\faceai\\"
local STRIDE, TABLE_OFF = 72, 0x50910
local seq = 0
local ctx_ref
-- Reads that fail return nil instead of raising (Sider has no usable pcall; ReadProcessMemory through the global ffi,
-- available with luajit.ext.enabled = 1).
local rd = function(a, n) local ok, r = true, nil; if pcall then ok, r = pcall(memory.read, a, n) else r = memory.read(a, n) end; return ok and r or nil end
do
  local F = ffi   -- global only with luajit.ext.enabled (no rawget in Sider Lua)
  if F then
    local ok0 = pcall and pcall(F.cdef, [[
      void* FP_GetCurrentProcess(void) __asm__("GetCurrentProcess");
      int FP_ReadProcessMemory(void* h, const void* addr, void* buf, size_t n, size_t* got) __asm__("ReadProcessMemory");
    ]])
    local proc = F.C.FP_GetCurrentProcess()
    local buf, got = F.new("uint8_t[?]", 0x10000), F.new("size_t[1]")
    rd = function(addr, len)
      if type(addr) == "cdata" then addr = tonumber(F.cast("uint64_t", addr)) end
      if type(addr) ~= "number" or addr < 0x10000 or len <= 0 or len > 0x10000 then return nil end
      got[0] = 0
      if F.C.FP_ReadProcessMemory(proc, F.cast("const void*", addr), buf, len, got) == 0 or tonumber(got[0]) ~= len then return nil end
      return F.string(buf, len)
    end
  end
end


local function p64(addr) return memory.unpack("u64", memory.read(addr, 8)) end

function m.dump()
  seq = seq + 1
  local name = string.format("dump_%s_%02d.bin", os.date("%H%M%S"), seq)
  local info = memory.get_process_info()
  local base = info.base or info.base_address
  local app = p64(p64(base + 0x3705E10) + 0x60)
  local c_new = memory.unpack("u16", memory.read(app + 0x4c7252, 2))
  local c_old = memory.unpack("u16", memory.read(app + 0x260552, 2))
  local n = (c_new > 0 and c_new <= 64999) and c_new or c_old
  log(string.format("faceai_probe: app=%x count_appcap=%d count_old=%d -> dumping %d records", tonumber(app), c_new, c_old, n))
  local f = io.open(ctx_ref.sider_dir .. OUT .. name, "wb")
  if not f then log("faceai_probe: cannot open " .. OUT .. " (create the folder content\\faceai)"); return end
  for i = 0, n - 1, 1024 do
    local c = math.min(1024, n - i)
    f:write(memory.read(app + TABLE_OFF + i * STRIDE, c * STRIDE))
  end
  f:close()
  log("faceai_probe: written " .. name .. " (" .. n * STRIDE .. " bytes)")
end

-- F6: where does the game keep the PLAYER table (0x17C bytes per player)? Needs players_dump.meta from this game launch
-- (F7 in PlayerDump). Looks for pointers, two levels below [exe+0x3705E10], that point at or just before the table, so the
-- chain can be hard-coded and the F7 step goes away. Result goes to sider.log.
local function hex(h) local v = 0 for c in h:gmatch(".") do v = v * 16 + tonumber(c, 16) end return v end
function m.find_players()
  local f = io.open(ctx_ref.sider_dir .. META, "r")
  if not f then log("faceai_probe: players_dump.meta not found, press F7 in PlayerDump first"); return end
  local t = f:read("*a"); f:close()
  local first = hex(t:match("first_addr=0x(%x+)") or "0")
  log(string.format("faceai_probe: player table first_addr = 0x%X", first))
  local info = memory.get_process_info()
  local base = info.base or info.base_address
  local function u64(a) local r = rd(a, 8); return r and memory.unpack("u64", r) or nil end
  local function num(v) return v and tonumber(v) end
  local obj = num(u64(num(base) + 0x3705E10))
  log(string.format("faceai_probe: obj = 0x%X", obj or 0))
  local hits = 0
  local function check(where, v)
    v = num(v)
    if v and v >= 0x10000 and v <= first and first - v <= 0x4000000 then
      hits = hits + 1
      log(string.format("faceai_probe: CANDIDATE %s = 0x%X  (table at pointer + 0x%X)", where, v, first - v))
    end
  end
  for o1 = 0, 0x400, 8 do
    local p1 = num(u64(obj + o1))
    check(string.format("[obj+0x%X]", o1), p1)
    if p1 and p1 >= 0x10000 and p1 < 0x7FFFFFFFFFFF then
      for o2 = 0, 0x400, 8 do check(string.format("[[obj+0x%X]+0x%X]", o1, o2), u64(p1 + o2)) end
    end
  end
  log("faceai_probe: player table search done, " .. hits .. " candidate(s)")
end

function m.key_down(ctx, vkey)
  if vkey == 0x77 then m.dump() elseif vkey == 0x75 then m.find_players() end
end
function m.overlay_on(ctx) return "faceai_probe: F8 = dump appearance table, F6 = find player table (" .. seq .. " dumps so far)" end
function m.init(ctx) ctx_ref = ctx; ctx.register("key_down", m.key_down); ctx.register("overlay_on", m.overlay_on); log("faceai_probe loaded: F8 dumps the appearance table") end
return m
