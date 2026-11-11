--[[
problems – collects the problems that a filter finds, not a filter itself

Each problem names the building block it's in, from the <!-- edit:... --> comments of the
Markdown, or the bibliography entry, if known. All problems are reported together at the end.
A filter that runs before others can save its problems instead, so that the last one reports them all.

    local problems = dofile(pandoc.path.join({ pandoc.path.directory(PANDOC_SCRIPT_FILE), "problems.lua" }))
    return { problems.filter({ Link = check_link }), problems.report }
]]

local M = {}

-- The metadata that carries the saved problems to the filter that reports them
local SAVED = "ceos-ard-problems"

local found = {}
local reported = {}
local source = nil

function M.add(message)
  local line = source and (source .. ": " .. message) or message
  if not reported[line] then
    reported[line] = true
    table.insert(found, line)
  end
end

local function track_raw(el)
  local marker = el.text:match("^<!%-%-%s*edit:%s*(.-)%s*%-%->$")
  if marker then
    source = marker
  end
end

local function track_header(el)
  -- The marker is inside the heading, but the heading is visited before its content
  el.content:walk({ RawInline = track_raw })
end

local function track_div(el)
  -- citeproc puts each entry of the bibliography in a div with the id ref-<key>
  local key = el.identifier:match("^ref%-(.+)$")
  if key then
    source = "bibliography entry '" .. key .. "'"
  end
end

local TRACKERS = { RawBlock = track_raw, RawInline = track_raw, Header = track_header, Div = track_div }

-- A top-down filter with the given functions, which knows the building block of each element
function M.filter(functions)
  local filter = { traverse = "topdown" }
  for name, track in pairs(TRACKERS) do
    local check = functions[name]
    filter[name] = function(el)
      track(el)
      if check then
        return check(el)
      end
    end
  end
  for name, check in pairs(functions) do
    if not TRACKERS[name] then
      filter[name] = check
    end
  end
  return filter
end

M.save = {
  Pandoc = function(doc)
    doc.meta[SAVED] = pandoc.MetaList(found)
    return doc
  end,
}

M.report = {
  Pandoc = function(doc)
    local all = {}
    for _, line in ipairs(doc.meta[SAVED] or {}) do
      table.insert(all, pandoc.utils.stringify(line))
    end
    for _, line in ipairs(found) do
      table.insert(all, line)
    end
    if #all > 0 then
      error("\n" .. table.concat(all, "\n") .. "\n", 0)
    end
    doc.meta[SAVED] = nil
    return doc
  end,
}

return M
