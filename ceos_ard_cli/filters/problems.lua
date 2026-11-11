--[[
problems – collects the problems that a filter finds, not a filter itself

Each problem names the building block it's in, from the <!-- edit:... --> comments of the
Markdown, or the bibliography entry, if known. All problems are reported together at the end.

    local problems = dofile(pandoc.path.join({ pandoc.path.directory(PANDOC_SCRIPT_FILE), "problems.lua" }))
    return { problems.filter({ Link = check_link }), problems.report }
]]

local M = {}

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
        check(el)
      end
    end
  end
  for name, check in pairs(functions) do
    if not TRACKERS[name] then
      filter[name] = function(el)
        check(el)
      end
    end
  end
  return filter
end

M.report = {
  Pandoc = function()
    if #found == 0 then
      return
    end
    error("\n" .. table.concat(found, "\n") .. "\n", 0)
  end,
}

return M
