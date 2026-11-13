--[[
bibliography – add an edit marker to each entry of the bibliography

citeproc puts each entry in a div with the id ref-<key>, the key is the name of the file in
the references folder. Runs after citeproc and after the filters that check the content.
]]

if not FORMAT:match("html") then
  return {}
end

return {
  {
    Div = function(el)
      -- Runs after sanitize.lua: only the characters that the server allows in edit paths, they can't end the comment
      local key = el.identifier:match("^ref%-([%w_.~:%-]+)$")
      if key then
        el.content:insert(1, pandoc.RawBlock("html", "<!-- edit:references/" .. key .. ".bib -->"))
        return el
      end
    end,
  },
}
