--[[
links – refuse links and images that are broken in the documents

A link needs one of the known schemes, or points to an anchor or to a file in the
assets folder, the only folder that is published with the documents. An image must
be a file in the assets folder or a data URI. Runs after citeproc, so that it also
checks the links that citeproc creates from the bibliography. Relative paths are
resolved from the input folder.
]]

local problems = dofile(pandoc.path.join({ pandoc.path.directory(PANDOC_SCRIPT_FILE), "problems.lua" }))

local SCHEMES = { "http", "https", "mailto", "ftp", "ftps", "sftp", "s3" }
local ASSETS = "assets/"

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

-- The path of a file in the assets folder, or nil
local function asset(target)
  -- Decoded after removing the query and fragment, as an encoded ? or # is part of the file name
  local path = decode((target:gsub("[?#].*$", ""))):gsub("^%./", "")
  if path:sub(1, #ASSETS) ~= ASSETS then
    return nil
  end
  for part in path:gmatch("[^/\\]+") do
    if part == ".." then
      return nil
    end
  end
  return path
end

local function check_link(el)
  local target = el.target
  local scheme = target:match("^(%a[%w+.-]*):")
  if scheme then
    if not is_scheme(scheme:lower()) then
      problems.add("Links must use one of the schemes " .. table.concat(SCHEMES, ", ") .. ", found '" .. target .. "'")
    end
  elseif target == "" then
    problems.add("Links need a target, found one for '" .. pandoc.utils.stringify(el.content) .. "'")
  elseif not target:match("^#") then
    local path = asset(target)
    if not path then
      local hint = looks_like_domain(target) and " (did you mean 'https://" .. target .. "'?)" or ""
      problems.add("Links must point to a file in the assets folder, found '" .. target .. "'" .. hint)
    elseif not exists(path) then
      problems.add("The linked file doesn't exist: '" .. target .. "'")
    end
  end
end

local function check_image(el)
  if el.src:match("^data:") then
    return
  end
  local path = asset(el.src)
  if not path then
    problems.add("Images must be files in the assets folder, found '" .. el.src .. "'")
  elseif not exists(path) then
    problems.add("The image doesn't exist: '" .. el.src .. "'")
  end
end

return { problems.filter({ Link = check_link, Image = check_image }), problems.report }
