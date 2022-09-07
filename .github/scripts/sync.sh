# configure git
git config --local user.email 1589480+BrewTestBot@users.noreply.github.com
git config --local user.name BrewTestBot
git config --local pull.rebase true

trunk=https://raw.githubusercontent.com/Homebrew/homebrew-core/master/Formula
mapfile -t extensions < <(find ./Formula -maxdepth 1 -name "*@*.rb" -print0 | xargs -0 basename -a | sed "s/@.*//" | sort | uniq)
for extension in "${extensions[@]}"; do
  formula_file=./Formula/"$extension"@7.2.rb
  if ! [ -e "$formula_file" ]; then
    formula_file=./Formula/"$extension"@7.4.rb
  fi
  mapfile -t deps < <(grep "depends_on" "$formula_file" | tr -d '"' | cut -d' ' -f 4)
  if [ "$extension" = "vips" ]; then
    curl -o $(brew --repo homebrew/core)/Formula/vips.rb -sL "$trunk"/vips.rb
    mapfile -t vips_deps < <(brew deps vips)
    deps=( "${deps[@]}" "${vips_deps[@]}" )
  fi  
  
  if [[ -n "${deps// }" ]]; then
    printf "\n----- %s -----\n" "$extension"
    echo "${deps[@]//shivammathur*}"
    sudo mkdir -p "./.github/deps/$extension"
    for formula in "${deps[@]//shivammathur*}"; do
      [ "$formula" = "python" ] && continue;
      if [ "x$formula" != "x" ]; then
        sudo curl -o "./.github/deps/$extension/$formula.rb" -sL "$trunk"/"$formula".rb
        grep -q "Formula" "./.github/deps/$extension/$formula.rb" || exit 1
      fi
    done
    ls "./.github/deps/$extension"
  fi
done
sudo git status
sudo git add .
if [ "$(git status --porcelain=v1 2>/dev/null | wc -l)" != "0" ]; then
  sudo git stash
  sudo git pull -f https://"$GITHUB_REPOSITORY_OWNER":"$GITHUB_TOKEN"@github.com/"$GITHUB_REPOSITORY".git master
  sudo git stash apply
  sudo git add .
  sudo git commit -m "Update extension dependencies"
  sudo git push -f https://"$GITHUB_REPOSITORY_OWNER":"$GITHUB_TOKEN"@github.com/"$GITHUB_REPOSITORY".git master || true
fi
