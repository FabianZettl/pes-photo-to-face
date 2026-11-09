-- faceai: writes slider values into the in-memory PlayerAppearance table.
--   content\faceai\faceai.csv       queue: "Id,<Slider>,...[,Template]", F9 imports it and removes the imported rows
--   content\faceai\faceai_done.csv  everything imported so far (same columns for all rows). Players WITHOUT an
--                                     appearance record (new-world players) have none after a restart, so F9 inserts
--                                     them again from this file every session.
-- F9 apply | F10 snapshot | F11 find the player on screen (change one slider in between).
-- A player without a record gets a new record: a copy of the record of "Template" (player id, column optional,
-- default DEFAULT_TEMPLATE) with his id and the sliders; records stay sorted by id, the count (u16) grows by one.
-- EXPERIMENTAL: not verified in game; memory only (a restart undoes it).
local m = {}
local CSV = "content\\faceai\\faceai.csv"
local DONE = "content\\faceai\\faceai_done.csv"
local NW = "content\\faceai\\faceai_newworld.csv"      -- written by the tool's "New World" tab (Sync)
local SIG = "content\\faceai\\faceai_world.sig"        -- path of fl26playerids.json + fingerprint of the build the NW ids belong to
local STRIDE, TABLE_OFF, CAP = 72, 0x50910, 64999
local EDITED_FLAG_BIT = 32
local DEFAULT_TEMPLATE = 178371
local LAYOUT = {
  ["SkinColour"]={360,3,0,0,6},
  ["HeadLength"]={140,4,7,-7,7},
  ["HeadWidth"]={144,4,7,-7,7},
  ["FaceHeight"]={412,4,7,-7,7},
  ["FaceSize"]={408,4,7,-7,7},
  ["UpperEyelidType"]={379,3,0,1,7},
  ["BottomEyelidType"]={384,3,-1,1,7},
  ["EyeHeight"]={288,4,7,-7,7},
  ["HorizontalEyePosition"]={284,4,7,-7,7},
  ["IrisColour"]={512,4,-1,0,11},
  ["PupilSize"]={236,4,7,-7,7},
  ["UpperEyelidHt.(Inner)"]={264,4,7,-7,7},
  ["UpperEyelidWd.(Inner)"]={260,4,7,-7,7},
  ["UpperEyelidHt.(Outer)"]={272,4,7,-7,7},
  ["UpperEyelidWd.(Outer)"]={268,4,7,-7,7},
  ["InnerEyeHeight"]={248,4,7,-7,7},
  ["InnerEyePosition"]={244,4,7,-7,7},
  ["EyeCornerHeight"]={256,4,7,-7,7},
  ["OuterEyePosition"]={252,4,7,-7,7},
  ["BottomEyelidHeight"]={280,4,7,-7,7},
  ["Forehead"]={368,3,-1,1,7},
  ["EyebrowType"]={400,3,-1,1,8},
  ["EyebrowThickness"]={478,2,0,0,2},
  ["EyebrowStyle"]={462,2,0,0,2},
  ["EyebrowDensity"]={470,2,0,0,3},
  ["InnerEyebrowHeight"]={216,4,7,-7,7},
  ["BrowWidth"]={212,4,7,-7,7},
  ["OuterEdyebrowHeight"]={228,4,7,-7,7},
  ["TempleWidth"]={224,4,7,-7,7},
  ["NoseType"]={416,3,-1,1,8},
  ["LaughterLines"]={376,3,-1,1,5},
  ["NoseHeight"]={292,4,7,-7,7},
  ["NostrilWidth"]={300,4,7,-7,7},
  ["NoseWidth"]={312,4,7,-7,7},
  ["UpperLipType"]={424,3,-1,1,5},
  ["LowerLipType"]={427,3,-1,1,5},
  ["MouthPosition"]={320,4,7,-7,7},
  ["LipSize"]={328,4,7,-7,7},
  ["LipWidth"]={340,4,7,-7,7},
  ["MouthCornerHeight"]={336,4,7,-7,7},
  ["FacialHairType"]={371,5,0,0,19},
  ["Thickness"]={510,2,0,0,3},
  ["CheekType"]={363,3,-1,1,6},
  ["NeckLineType"]={405,2,-1,1,4},
  ["Cheekbones"]={192,4,7,-7,7},
  ["ChinHeight"]={352,4,7,-7,7},
  ["ChinWidth"]={348,4,7,-7,7},
  ["JawHeight"]={184,4,7,-7,7},
  ["Jawline"]={180,4,7,-7,7},
  ["EarLength"]={388,4,7,-7,7},
  ["EarWidth"]={392,4,7,-7,7},
  ["EarAngle"]={396,4,7,-7,7},
  ["HeadDepth"]={148,4,7,-7,7},
  ["EyeDepth"]={240,4,7,-7,7},
  ["EyebrowDepth"]={232,4,7,-7,7},
  ["NoseTipDepth"]={296,4,7,-7,7},
  ["NoseDepth"]={308,4,7,-7,7},
  ["MouthDepth"]={324,4,7,-5,7},
  ["ChinDepth"]={356,4,7,-7,7},
  ["EyebrowColourR"]={456,6,0,0,63},
  ["EyebrowColourG"]={464,6,0,0,63},
  ["EyebrowColourB"]={472,6,0,0,63},
  ["FacialHairColourR"]={492,6,0,0,63},
  ["FacialHairColourG"]={498,6,0,0,63},
  ["FacialHairColourB"]={504,6,0,0,63},
  ["HairStyle"]={448,3,0,0,7},
  ["HairLength"]={480,3,0,0,5},
  ["HairCurl"]={483,3,1,0,6},
  ["HairColourR"]={430,6,0,0,63},
  ["HairColourG"]={436,6,0,0,63},
  ["HairColourB"]={442,6,0,0,63},
  ["HairColourType"]={524,3,0,0,7},
  ["HairFront"]={528,2,0,1,3},
  ["HairParting"]={531,3,0,1,6},
  ["HairHairline"]={537,2,0,1,3},
  ["HairForehead"]={540,2,0,1,3},
  ["HairBack"]={534,3,0,1,4},
}

local NAMES = {}
for k in pairs(LAYOUT) do NAMES[#NAMES + 1] = k end
table.sort(NAMES)
NAMES[#NAMES + 1] = "Template"
local CANON = "Id," .. table.concat(NAMES, ",")

local ctx_ref, last = nil, "F9 = apply faceai.csv"
local probes = {}
local viewed, snap, snap_n = nil, nil, 0

local function any(t) for _ in pairs(t) do return true end return false end

-- Sider has no real pcall in some setups; same shim idea as the fl26 modules.
local real_pcall = pcall ~= nil
local pcall = pcall
if not pcall then
  if xpcall then
    pcall = function(f, ...) local a = {...}; return xpcall(function() return f(unpack(a)) end, function(e) return e end) end
  else
    pcall = function(f, ...) return true, f(...) end
  end
end

-- Reads that fail return nil instead of raising (the tick runs from the first frame on, before the game has built its
-- tables). With luajit.ext.enabled the global ffi gives ReadProcessMemory; without it memory.read is used as it is.
local safe_reads = real_pcall   -- can a failed read be survived? (ffi ReadProcessMemory or a real pcall)
local num = function(a) return a end
local rd = function(a, n) local ok, s = pcall(memory.read, a, n); return ok and s or nil end
do
  local F = ffi   -- global only with luajit.ext.enabled (no rawget in Sider Lua)
  if F then
    pcall(F.cdef, [[
      void* FA_GetCurrentProcess(void) __asm__("GetCurrentProcess");
      int FA_ReadProcessMemory(void* h, const void* addr, void* buf, size_t n, size_t* got) __asm__("ReadProcessMemory");
    ]])
    local ok, proc = pcall(function() return F.C.FA_GetCurrentProcess() end)
    if ok and proc then
      local buf, got, cap = F.new("uint8_t[?]", 0x10000), F.new("size_t[1]"), 0x10000
      num = function(a)
        if type(a) == "cdata" then local k, v = pcall(function() return tonumber(F.cast("uint64_t", a)) end); return k and v or a end
        return tonumber(a) or a
      end
      safe_reads = true
      rd = function(addr, len)
        addr = num(addr)
        if type(addr) ~= "number" or addr < 0x10000 or len <= 0 or len > 0x4000000 then return nil end
        if len > cap then cap = len; buf = F.new("uint8_t[?]", cap) end
        got[0] = 0
        if F.C.FA_ReadProcessMemory(proc, F.cast("const void*", addr), buf, len, got) == 0 or tonumber(got[0]) ~= len then return nil end
        return F.string(buf, len)
      end
    end
  end
end

local function slurp(path)
  local f = io.open(ctx_ref.sider_dir .. path, "r")
  if not f then return "" end
  local t = f:read("*a"); f:close()
  return t
end

local function p64(a)
  local s = rd(a, 8)
  return s and memory.unpack("u64", s) or nil
end

local function split(line)
  local t = {}
  for f in (line:gsub("\r", "") .. ","):gmatch("([^,]*),") do t[#t + 1] = f end
  return t
end

-- CSV -> rows[id] = {name = number}, raw[id] = line, header line; nil when the file is missing
local function load_csv(path)
  local f = io.open(ctx_ref.sider_dir .. path, "r")
  if not f then return nil end
  local hline = (f:read("*l") or ""):gsub("\r", "")
  local head, rows, raw = split(hline), {}, {}
  for line in f:lines() do
    line = line:gsub("\r", "")
    if line:match("%S") then
      local c, r = split(line), {}
      for i = 2, #head do if c[i] and c[i] ~= "" then r[head[i]] = tonumber(c[i]) end end
      local id = tonumber(c[1])
      if id then rows[id] = r; raw[id] = line end
    end
  end
  f:close()
  return rows, raw, hline
end

local function canon_line(id, r)
  local t = {tostring(id)}
  for i, k in ipairs(NAMES) do t[#t + 1] = r[k] ~= nil and tostring(r[k]) or "" end
  return table.concat(t, ",")
end

local function setbits(rec, pos, w, val)   -- rec: table of bytes, bit i = byte i//8, bit i%8 (LSB first)
  for k = 0, w - 1 do
    local p = pos + k
    local b, o = math.floor(p / 8) + 1, p % 8
    local on = math.floor(val / 2 ^ k) % 2 == 1
    local cur = math.floor(rec[b] / 2 ^ o) % 2 == 1
    if on ~= cur then rec[b] = rec[b] + (on and 2 ^ o or -(2 ^ o)) end
  end
end

local function with_sliders(s, row)   -- 72-byte record string -> same with the sliders of row
  local rec, cnt = {s:byte(1, STRIDE)}, 0
  -- a custom hair colour only shows when the colour preset is 0 (preset 1..7 = the game's palette)
  local custom = row.HairColourType == nil and (row.HairColourR or row.HairColourG or row.HairColourB)
  for name, L in pairs(LAYOUT) do
    local v = row[name]
    if name == "HairColourType" and custom then v = 0 end
    if v then
      v = math.max(L[4], math.min(L[5], math.floor(v + 0.5)))
      setbits(rec, L[1], L[2], v + L[3])
      cnt = cnt + 1
    end
  end
  setbits(rec, EDITED_FLAG_BIT, 1, 1)
  return string.char(unpack(rec)), cnt
end

local function table_info()   -- app, first record, count; nil while the game has no (plausible) table yet
  local info = memory.get_process_info()
  local obj = p64(num(info.base or info.base_address) + 0x3705E10)
  local app = obj and obj ~= 0 and p64(num(obj) + 0x60)
  if not app or num(app) < 0x10000 then return nil end
  local c = rd(num(app) + 0x4c7252, 2)
  local n = c and memory.unpack("u16", c) or 0
  if n < 1 or n > CAP then return nil end
  return num(app), num(app) + TABLE_OFF, n
end

local function read_records(base, n)   -- recs[0..n-1] = 72-byte strings; nil if any read fails
  local recs = {}
  for i = 0, n - 1, 1024 do
    local c = math.min(1024, n - i)
    local s = rd(base + i * STRIDE, c * STRIDE)
    if not s then return nil end
    for j = 0, c - 1 do recs[i + j] = s:sub(j * STRIDE + 1, (j + 1) * STRIDE) end
  end
  return recs
end

local function rec_id(s) return memory.unpack("u32", s:sub(1, 4)) end

-- New-world rows carry the game ids of ONE Mod Studio build (the ids are handed out at Build and can change). The tool
-- stores a fingerprint of that build's fl26playerids.json; the rows are used only while the file still has it.
local function fingerprint(data)   -- same as pesface/newworld.py: h = (h * 31 + byte) mod 2^32
  local h = 0
  for i = 1, #data do h = (h * 31 + data:byte(i)) % 4294967296 end
  return h
end
local world_t, world_ok_v, world_why = -100, false, ""
local function world_ok()
  if os.clock() - world_t < 30 then return world_ok_v, world_why end
  world_t = os.clock()
  local sigtxt = slurp(SIG)
  local path, hash = sigtxt:match("([^\r\n]+)[\r\n]+(%d+)")
  if not path then world_ok_v, world_why = false, "no faceai_world.sig (press Sync in the tool)"
  else
    local data = slurp(path)
    if data == "" then world_ok_v, world_why = false, "cannot read " .. path
    elseif tostring(fingerprint(data)) == hash then world_ok_v, world_why = true, ""
    else world_ok_v, world_why = false, "the Mod Studio build changed since the last Sync: press Sync in the tool" end
  end
  return world_ok_v, world_why
end

-- Which player is on screen? F10 snapshot, change any slider of that player in Edit, F11: the one record that
-- differs is the player. A CSV row with Id 0 goes to him.
function m.snapshot()
  local _, base, n = table_info()
  local recs = base and read_records(base, n)
  if not recs then last = "appearance table not readable yet"; return end
  snap, snap_n = recs, n
  last = "snapshot taken (" .. n .. " records): change a slider, then F11"
end
function m.find()
  if not snap then last = "press F10 first"; return end
  local _, base, n = table_info()
  local now, hits = base and read_records(base, n), {}
  if not now then last = "appearance table not readable"; return end
  for i = 0, math.min(n, snap_n) - 1 do if now[i] ~= snap[i] then hits[#hits + 1] = rec_id(now[i]) end end
  if #hits == 1 then viewed = hits[1]; last = "player on screen: " .. viewed
  else last = #hits .. " records changed, expected 1"; viewed = nil end
  log("faceai: " .. last)
  snap = now
end

function m.apply(silent)   -- returns true when done or nothing to do, false while the table is not ready
  local q, qraw, qhead = load_csv(CSV)
  local d, draw = load_csv(DONE)
  q, qraw, d, draw = q or {}, qraw or {}, d or {}, draw or {}
  local nwrows, nwset = load_csv(NW), {}   -- nwset: ids that came from the new-world file (never copied to done: they are tied to a build)
  if nwrows and any(nwrows) then
    local ok, why = world_ok()
    if ok then for id, r in pairs(nwrows) do d[id] = r; nwset[id] = true end
    elseif not silent or why ~= m.nw_warned then m.nw_warned = why; log("faceai: new-world rows skipped: " .. why) end
  end
  if not any(q) and not any(d) then
    if not silent then last = "nothing to do (" .. CSV .. " empty or missing)"; log("faceai: " .. last) end
    return true
  end
  if q[0] then   -- a row with Id 0 goes to the player on screen
    if viewed then q[viewed], qraw[viewed] = q[0], qraw[0] else log("faceai: row 0 skipped, press F10, change a slider, F11") end
    q[0], qraw[0] = nil, nil
  end
  local app, base, n = table_info()
  local recs = app and read_records(base, n)
  if not recs then
    if not silent then last = "appearance table not ready"; log("faceai: " .. last) end
    return false
  end
  local pos, sorted = {}, true
  for i = 0, n - 1 do
    local id = rec_id(recs[i]); pos[id] = i
    if i > 0 and id <= rec_id(recs[i - 1]) then sorted = false end
  end
  -- what to do: queue rows; plus done rows of players without a record or with an unedited one, unless the queue has them
  local todo = {}
  -- (bit 32 = "edited" flag: a record without it is still the game's default, so a done row is applied again)
  for id, r in pairs(d) do
    local i = pos[id]
    if not i or recs[i]:byte(5) % 2 == 0 then todo[id] = r end
  end
  for id, r in pairs(q) do todo[id] = r end
  local changed, added, applied, skipped = {}, {}, {}, {}
  for id, row in pairs(todo) do
    local i = pos[id]
    if i then
      recs[i] = with_sliders(recs[i], row); changed[i] = true; applied[id] = true
    else
      local t = recs[pos[row.Template or DEFAULT_TEMPLATE] or 0]
      local s = memory.pack("u32", id) .. with_sliders(t, row):sub(5)
      added[#added + 1] = {id = id, rec = s}; applied[id] = true
    end
  end
  table.sort(added, function(a, b) return a.id < b.id end)
  if #added > 0 and (not sorted or n + #added > CAP) then
    log(string.format("faceai: %d player(s) without record NOT inserted (%s)", #added,
        sorted and "table full" or "table is not sorted by id"))
    for _, a in ipairs(added) do applied[a.id], skipped[#skipped + 1] = nil, a.id end
    added = {}
  end
  if #added == 0 then
    for i in pairs(changed) do memory.write(base + i * STRIDE, recs[i]) end
  else   -- merge the new records in id order and write the whole table, then the count
    local out, k = {}, 1
    for i = 0, n - 1 do
      while added[k] and added[k].id < rec_id(recs[i]) do out[#out + 1] = added[k].rec; k = k + 1 end
      out[#out + 1] = recs[i]
    end
    while added[k] do out[#out + 1] = added[k].rec; k = k + 1 end
    memory.write(base, table.concat(out))
    memory.write(app + 0x4c7252, string.char((n + #added) % 256, math.floor((n + #added) / 256)))
  end
  for id in pairs(applied) do log(string.format("faceai: player %d %s", id, pos[id] and "updated" or "inserted (new record)")) end
  -- queue: drop the imported rows; done: add/replace them
  local keep, done = {}, {}
  for id, line in pairs(qraw) do if not applied[id] then keep[#keep + 1] = line end end
  for id, r in pairs(d) do if not nwset[id] then done[id] = canon_line(id, r) end end
  for id in pairs(applied) do if q[id] then done[id] = canon_line(id, q[id]) end end
  local ids = {}
  for id in pairs(done) do ids[#ids + 1] = id end
  table.sort(ids)
  local dl = {}
  for _, id in ipairs(ids) do dl[#dl + 1] = done[id] end
  local w = io.open(ctx_ref.sider_dir .. DONE, "w")
  if w then w:write(CANON, "\r\n", #dl > 0 and table.concat(dl, "\r\n") .. "\r\n" or ""); w:close() end
  if any(qraw) or any(q) then
    local qw = io.open(ctx_ref.sider_dir .. CSV, "w")
    if qw then qw:write(qhead or CANON, "\r\n", #keep > 0 and table.concat(keep, "\r\n") .. "\r\n" or ""); qw:close()
    else log("faceai: cannot rewrite " .. CSV) end
  end
  local na = 0 for _ in pairs(applied) do na = na + 1 end
  last = string.format("%d player(s): %d inserted, %d skipped; %d left in queue", na, #added, #skipped, #keep)
  log("faceai: " .. last)
  -- remember a few written records: if the game later rebuilds its table they lose the edited flag, and the tick
  -- notices and writes everything again
  probes = {}
  local app2, base2, n2 = table_info()
  local now = app2 and read_records(base2, n2)
  if now then
    for i = 0, n2 - 1 do
      local id = rec_id(now[i])
      if applied[id] and #probes < 3 then probes[#probes + 1] = {id = id, addr = base2 + i * STRIDE} end
    end
  end
  return true
end

-- Automatic run: every ~3 s from display_frame. Applies when the queue/done files changed, when the game has a new
-- table, or when one of our records was reset; otherwise it does nothing. No key press needed.
local tick_t, a_sig, a_app = -10, nil, nil
function m.tick()
  if not safe_reads then return end   -- without ffi/pcall an early read could raise every frame: F9 only
  local now = os.clock()
  if now - tick_t < 3 then return end
  tick_t = now
  local app = table_info()
  if not app then return end   -- game not loaded yet
  local sig = slurp(CSV) .. "|" .. slurp(DONE) .. "|" .. slurp(NW) .. "|" .. slurp(SIG)
  local reset = false
  for _, pr in ipairs(probes) do
    local s = rd(pr.addr, STRIDE)
    if not s or rec_id(s) ~= pr.id or s:byte(5) % 2 == 0 then reset = true end
  end
  if sig == a_sig and app == a_app and not reset then return end
  if m.apply(true) then
    a_sig, a_app = slurp(CSV) .. "|" .. slurp(DONE) .. "|" .. slurp(NW) .. "|" .. slurp(SIG), app   -- apply rewrites the files: remember the new state
  end
end

function m.key_down(ctx, vkey)
  if vkey == 0x78 then m.apply() elseif vkey == 0x79 then m.snapshot() elseif vkey == 0x7A then m.find() end
end
function m.overlay_on(ctx) return "faceai [F9 apply | F10 snapshot | F11 find player]: " .. last .. "   |   player: " .. tostring(viewed) end
-- fl26regen reads modules\fl26world.txt once in its init and gives every id of its "newfaces" lines a pack face,
-- which hides the slider face. So this module has to be listed BEFORE fl26regen.lua in sider.ini: here the ids
-- we manage (queue + done) are taken out of those lines first (original kept once as fl26world.txt.faceai-orig).
local function strip_world()
  local ex = {}
  for _, path in ipairs({CSV, DONE, NW}) do
    local rows = load_csv(path)
    if rows and (path ~= NW or world_ok()) then for id in pairs(rows) do ex[id] = true end end
  end
  if not any(ex) then return end
  local path = ctx_ref.sider_dir .. "modules\\fl26world.txt"
  local f = io.open(path, "r")
  if not f then return end
  local text = f:read("*a"); f:close()
  local removed, out = 0, {}
  for line in (text .. "\n"):gmatch("([^\n]*)\n") do
    local kind, rest = line:gsub("\r", ""):match("^(%s*newfaces3?d?)%s+(.*)$")
    if kind then
      local toks = {}
      for a, b in rest:gmatch("(%d+)%-?(%d*)") do
        local lo = tonumber(a); local hi = b ~= "" and tonumber(b) or lo
        local start
        for id = lo, hi + 1 do
          if id <= hi and not ex[id] then start = start or id
          else
            if id <= hi then removed = removed + 1 end
            if start then toks[#toks + 1] = (start == id - 1) and tostring(start) or (start .. "-" .. (id - 1)); start = nil end
          end
        end
      end
      line = kind .. " " .. table.concat(toks, " ") .. (line:sub(-1) == "\r" and "\r" or "")
    end
    out[#out + 1] = line
  end
  if out[#out] == "" then out[#out] = nil end
  if removed == 0 then return end
  local bak = io.open(path .. ".faceai-orig", "r")
  if bak then bak:close() else local b = io.open(path .. ".faceai-orig", "w"); if b then b:write(text); b:close() end end
  local w = io.open(path, "w")
  if w then w:write(table.concat(out, "\n"), "\n"); w:close(); log("faceai: " .. removed .. " id(s) taken out of fl26world.txt newfaces") end
end

function m.init(ctx)
  ctx_ref = ctx
  strip_world()
  ctx.register("key_down", m.key_down); ctx.register("overlay_on", m.overlay_on)
  pcall(ctx.register, "display_frame", m.tick)
  log("faceai loaded: applies " .. CSV .. " by itself (and on F9)")
end
return m
