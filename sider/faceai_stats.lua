-- faceai_stats: writes PES attributes from content\faceai\faceai_stats.csv into the game's player table.
-- CSV: header "Id,<Stat>,..." (OffensiveAwareness, Finishing, Speed, ... see FIELDS), values 40-99, any subset.
-- Find the table first: press F7 in PlayerDump once per game launch (it writes players_dump.meta with the table address),
-- then F5 here (module selected in the overlay). The table is rebuilt from the database at every start, so rows stay in
-- the CSV and are written again each launch.
-- Block layout (0x17C bytes per player, id at +0x30) and the field positions are the ones GrowthBridge (Karijera 26) uses:
-- each stat is 7 bits at a byte offset + shift inside a u32. EXPERIMENTAL: not verified in game yet; every write is read
-- back and logged, and a block is only written when its id matches.
local m = {}
local CSV = "content\\faceai\\faceai_stats.csv"
local META = "content\\ml-immersion\\bridge\\players_dump.meta"
local BLOCK = 0x17C
local FIELDS = {
  OffensiveAwareness = {0x03, 0},
  BallControl = {0x06, 5},
  Dribbling = {0x05, 6},
  TightPossession = {0x08, 0},
  Finishing = {0x08, 7},
  LowPass = {0x09, 6},
  LoftedPass = {0x0A, 5},
  Heading = {0x0C, 0},
  PlaceKicking = {0x0E, 5},
  Curl = {0x10, 0},
  Speed = {0x14, 7},
  Acceleration = {0x18, 7},
  KickingPower = {0x18, 0},
  Jump = {0x19, 6},
  PhysicalContact = {0x15, 6},
  Balance = {0x16, 5},
  Stamina = {0x1A, 5},
  DefensiveAwareness = {0x04, 0},
  BallWinning = {0x0C, 7},
  Aggression = {0x0D, 6},
  GKAwareness = {0x04, 7},
  GKCatching = {0x10, 7},
  GKClearing = {0x11, 6},
  GKReflexes = {0x12, 5},
  GKReach = {0x14, 0},
}
local ctx_ref, last = nil, "F5 = write stats (F7 in PlayerDump first)"

local function split(line)
  local t = {}
  for f in (line:gsub("\r", "") .. ","):gmatch("([^,]*),") do t[#t + 1] = f end
  return t
end

local function hex(h)   -- tonumber(x, 16) is cut at 32 bits in this Lua
  local v = 0
  for c in h:gmatch(".") do v = v * 16 + tonumber(c, 16) end
  return v
end

local function table_from_meta()
  local f = io.open(ctx_ref.sider_dir .. META, "r")
  if not f then return nil, "players_dump.meta not found: press F7 in PlayerDump first" end
  local t = f:read("*a"); f:close()
  local fa, st, n = t:match("first_addr=0x(%x+)"), t:match("stride=0x(%x+)"), tonumber(t:match("count=(%d+)") or "0")
  if not fa or not st or n == 0 then return nil, "players_dump.meta incomplete" end
  local s = hex(st)
  if s ~= BLOCK then return nil, string.format("unexpected stride 0x%X", s) end
  return hex(fa), n
end

local function build_index(base, n)
  local idx = {}
  for i = 0, n - 1, 256 do
    local c = math.min(256, n - i)
    local s = memory.read(base + i * BLOCK, c * BLOCK)
    for j = 0, c - 1 do idx[memory.unpack("u32", s:sub(j * BLOCK + 0x31, j * BLOCK + 0x34))] = base + (i + j) * BLOCK end
  end
  return idx
end

local function get(a, f)
  local v = memory.unpack("u32", memory.read(a + f[1], 4))
  return math.floor(v / 2 ^ f[2]) % 128
end

local function set(a, f, val)
  local cur = memory.unpack("u32", memory.read(a + f[1], 4))
  local low, high = 2 ^ f[2], 2 ^ (f[2] + 7)
  memory.write(a + f[1], memory.pack("u32", (cur % low) + math.floor(cur / high) * high + val * low))
  return get(a, f) == val
end

function m.apply()
  local f = io.open(ctx_ref.sider_dir .. CSV, "r")
  if not f then last = "cannot open " .. CSV; log("faceai_stats: " .. last); return end
  local head = split(f:read("*l") or "")
  local base, n = table_from_meta()
  if not base then f:close(); last = n; log("faceai_stats: " .. n); return end
  local idx = build_index(base, n)
  local players, written, bad = 0, 0, 0
  for line in f:lines() do
    local c = split(line)
    local id = tonumber(c[1])
    local a = id and idx[id]
    if a and memory.unpack("u32", memory.read(a + 0x30, 4)) == id then
      players = players + 1
      for i = 2, #head do
        local fld, v = FIELDS[head[i]], tonumber(c[i])
        if fld and v then
          v = math.max(40, math.min(99, math.floor(v + 0.5)))
          local old = get(a, fld)
          if set(a, fld, v) then
            written = written + 1
            if written <= 6 then log(string.format("faceai_stats: %d %s %d -> %d", id, head[i], old, v)) end
          else bad = bad + 1 end
        end
      end
    elseif id then log("faceai_stats: player " .. id .. " not in the table") end
  end
  f:close()
  last = string.format("%d player(s), %d values written, %d failed read-back", players, written, bad)
  log("faceai_stats: " .. last)
end

function m.key_down(ctx, vkey) if vkey == 0x74 then m.apply() end end
function m.overlay_on(ctx) return "faceai_stats [F5]: " .. last end
function m.init(ctx)
  ctx_ref = ctx
  ctx.register("key_down", m.key_down); ctx.register("overlay_on", m.overlay_on)
  log("faceai_stats loaded: F5 writes " .. CSV)
end
return m
