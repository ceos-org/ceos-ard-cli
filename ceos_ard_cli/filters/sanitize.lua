--[[
sanitize – refuse raw output, attributes and metadata that the content can't use

Raw output (e.g. HTML) and attributes (e.g. `poster` on a video) can make pandoc embed
files from anywhere into the documents, and metadata can make it read files or insert
raw output. Raw output and most attributes also only work in some of the formats.

Runs before all other filters, so it only sees the content, not the raw output and the
attributes that the other filters and citeproc create on purpose.
]]

local problems = dofile(pandoc.path.join({ pandoc.path.directory(PANDOC_SCRIPT_FILE), "problems.lua" }))

-- label is read by pandoc-crossref and no-sectionnumbers.lua, columns and widths by changelog-table.lua,
-- width and height work in all formats
local ATTRIBUTES = { label = true, columns = true, widths = true, width = true, height = true }

local function check_attributes(el)
  local keys = {}
  for key, _ in pairs(el.attributes) do
    table.insert(keys, key)
  end
  table.sort(keys)
  for _, key in ipairs(keys) do
    if not ATTRIBUTES[key:lower()] then
      problems.add("The attribute '" .. key .. "' is not allowed")
    end
  end
end

local function check_raw(el)
  -- The template marks the editable building blocks with comments, e.g. <!-- edit:pfs/x/document.yaml -->
  if not (el.format:match("^html") and el.text:match("^<!%-%-[^<>]*%-%->$")) then
    problems.add("Raw " .. el.format .. " is not allowed: " .. el.text:sub(1, 60))
  end
end

local function check_meta(meta)
  -- The CLI passes the keys of the template's front matter, as content could add others, e.g. css
  local allowed = {}
  for key in (os.getenv("CEOS_ARD_METADATA") or ""):gmatch("[^,]+") do
    allowed[key] = true
  end
  local keys = {}
  for key, _ in pairs(meta) do
    table.insert(keys, key)
  end
  table.sort(keys)
  for _, key in ipairs(keys) do
    if not allowed[key] then
      problems.add("The metadata '" .. key .. "' is not allowed")
    end
  end
end

return {
  { Meta = check_meta },
  problems.filter({
    RawBlock = check_raw,
    RawInline = check_raw,
    Header = check_attributes,
    Div = check_attributes,
    Span = check_attributes,
    Image = check_attributes,
    Link = check_attributes,
    CodeBlock = check_attributes,
    Code = check_attributes,
    Table = check_attributes,
    Figure = check_attributes,
  }),
  problems.report,
}
