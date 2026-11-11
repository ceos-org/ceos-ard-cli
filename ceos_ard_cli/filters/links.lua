--[[
links – refuse links that are broken in the documents

A link needs one of the known schemes, or points to an anchor or to a file in the
assets folder, the only folder that is published with the documents. Runs before
the other filters, so it only checks the links of the content, not the ones the
filters and citeproc create. Relative paths are resolved from the input folder.
]]

local SCHEMES = { "http", "https", "mailto", "ftp", "ftps", "sftp", "s3" }
local ASSETS = "assets/"

local function fail(message)
  error("\n" .. message .. "\n", 0)
end

local function is_scheme(name)
  for _, scheme in ipairs(SCHEMES) do
    if scheme == name then
      return true
    end
  end
  return false
end

local function decode(text)
  return (text:gsub("%%(%x%x)", function(hex) return string.char(tonumber(hex, 16)) end))
end

local function looks_like_domain(target)
  return target:match("^www%.") ~= nil or target:match("^[%w-]+%.[%w.-]*%a/") ~= nil
end

local function exists(path)
  local file = io.open(path, "rb")
  if file then
    file:close()
  end
  return file ~= nil
end

local function check_file(target)
  -- Decoded after removing the query and fragment, as an encoded ? or # is part of the file name
  local path = decode((target:gsub("[?#].*$", ""))):gsub("^%./", "")
  local outside = path:sub(1, #ASSETS) ~= ASSETS or path:match("^[/\\]")
  for part in path:gmatch("[^/\\]+") do
    if part == ".." then
      outside = true
    end
  end
  if outside then
    local hint = looks_like_domain(target) and " (did you mean 'https://" .. target .. "'?)" or ""
    fail("Links must point to a file in the assets folder, found '" .. target .. "'" .. hint)
  end
  if not exists(path) then
    fail("The linked file doesn't exist: '" .. target .. "'")
  end
end

function Link(el)
  local target = el.target
  local scheme = target:match("^(%a[%w+.-]*):")
  if scheme then
    if not is_scheme(scheme:lower()) then
      fail("Links must use one of the schemes " .. table.concat(SCHEMES, ", ") .. ", found '" .. target .. "'")
    end
  elseif target == "" then
    fail("Links need a target, found one for '" .. pandoc.utils.stringify(el.content) .. "'")
  elseif not target:match("^#") then
    check_file(target)
  end
end
