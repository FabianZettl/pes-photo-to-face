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
local viewed, snap, snap_n = nil, nil, 0

local function any(t) for _ in pairs(t) do return true end return false end

local function p64(a) return memory.unpack("u64", memory.read(a, 8)) end

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

local function table_info()
  local info = memory.get_process_info()
  local app = p64(p64((info.base or info.base_address) + 0x3705E10) + 0x60)
  return app, app + TABLE_OFF, memory.unpack("u16", memory.read(app + 0x4c7252, 2))
end

local function read_records(base, n)   -- recs[0..n-1] = 72-byte strings
  local recs = {}
  for i = 0, n - 1, 1024 do
    local c = math.min(1024, n - i)
    local s = memory.read(base + i * STRIDE, c * STRIDE)
    for j = 0, c - 1 do recs[i + j] = s:sub(j * STRIDE + 1, (j + 1) * STRIDE) end
  end
  return recs
end

local function rec_id(s) return memory.unpack("u32", s:sub(1, 4)) end

-- Which player is on screen? F10 snapshot, change any slider of that player in Edit, F11: the one record that
-- differs is the player. A CSV row with Id 0 goes to him.
function m.snapshot()
  local _, base, n = table_info()
  snap, snap_n = read_records(base, n), n
  last = "snapshot taken (" .. n .. " records): change a slider, then F11"
end
function m.find()
  if not snap then last = "press F10 first"; return end
  local _, base, n = table_info()
  local now, hits = read_records(base, n), {}
  for i = 0, math.min(n, snap_n) - 1 do if now[i] ~= snap[i] then hits[#hits + 1] = rec_id(now[i]) end end
  if #hits == 1 then viewed = hits[1]; last = "player on screen: " .. viewed
  else last = #hits .. " records changed, expected 1"; viewed = nil end
  log("faceai: " .. last)
  snap = now
end

function m.apply()
  local q, qraw, qhead = load_csv(CSV)
  local d, draw = load_csv(DONE)
  q, qraw, d, draw = q or {}, qraw or {}, d or {}, draw or {}
  if not any(q) and not any(d) then last = "nothing to do (" .. CSV .. " empty or missing)"; log("faceai: " .. last); return end
  if q[0] then   -- a row with Id 0 goes to the player on screen
    if viewed then q[viewed], qraw[viewed] = q[0], qraw[0] else log("faceai: row 0 skipped, press F10, change a slider, F11") end
    q[0], qraw[0] = nil, nil
  end
  local app, base, n = table_info()
  local recs = read_records(base, n)
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
  for id, r in pairs(d) do done[id] = canon_line(id, r) end
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
  for _, path in ipairs({CSV, DONE}) do
    local rows = load_csv(path)
    if rows then for id in pairs(rows) do ex[id] = true end end
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
  log("faceai loaded: F9 applies " .. CSV)
end
return m
