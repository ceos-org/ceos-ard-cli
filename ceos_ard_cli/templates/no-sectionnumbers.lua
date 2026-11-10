-- See also: https://github.com/lierdakil/pandoc-crossref/issues/230#issuecomment-2677186070

-- pandoc-crossref joins the section numbers and the labels of all parent sections into the link text
-- (e.g. 1.2.|Category.|Category: Title), which can't be split reliably as titles may contain any character.
-- So the generated link texts, which end with the label, are replaced with the label of the target section.
-- The labels start with a | for compatibility with filters that still split the link texts at it.
local labels = {}

local function collect_labels(header)
  local label = header.attributes["label"]
  if header.identifier:match("^sec:") and label then
    labels[header.identifier] = label
  end
end

local function replace_link_text(link)
  local label = labels[link.target:match("^#(sec:.+)$")]
  if label then
    local text = pandoc.utils.stringify(link.content)
    if text:sub(-#label) == label then
      link.content = pandoc.Inlines((label:gsub("^|", "")))
    end
  end
  return link
end

return {
  { Header = collect_labels },
  { Link = replace_link_text },
}
