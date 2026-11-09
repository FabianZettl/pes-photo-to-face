-- faceai_probe: READ-ONLY. F8 writes the in-memory PlayerAppearance table to content\faceai\appearance_mem_NN.bin (numbered per press)
-- (72 bytes per record) so the slider bit layout can be worked out offline. Changes nothing in the game.
-- Chain from fl26appcap.lua: obj = [exe+0x3705e10]; app = [obj+0x60]; table = app+0x50910;
-- u16 record count at app+0x4c7252 (with fl26appcap) or app+0x260552 (without).
local m = {}
local OUT = "content\\faceai\\"
local STRIDE, TABLE_OFF = 72, 0x50910
local seq = 0
local ctx_ref

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

function m.key_down(ctx, vkey) if vkey == 0x77 then m.dump() end end
function m.overlay_on(ctx) return "faceai_probe: F8 = dump appearance table (" .. seq .. " dumps so far)" end
function m.init(ctx) ctx_ref = ctx; ctx.register("key_down", m.key_down); ctx.register("overlay_on", m.overlay_on); log("faceai_probe loaded: F8 dumps the appearance table") end
return m
