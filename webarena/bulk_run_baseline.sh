# export WA_SHOPPING="http://3.142.84.141:7770"
# export WA_SHOPPING_ADMIN="http://3.142.84.141:7780/admin"
# export WA_REDDIT="http://3.142.84.141:9999"
# export WA_GITLAB="http://3.142.84.141:8023"
# export WA_WIKIPEDIA="http://3.142.84.141:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
# export WA_MAP="http://3.142.84.141:3000"
# export WA_HOMEPAGE="http://3.142.84.141:4399"

export WA_SHOPPING="http://10.10.0.120:7770"
export WA_SHOPPING_ADMIN="http://10.10.0.120:7780/admin"
export WA_REDDIT="http://10.10.0.120:9999"
export WA_GITLAB="http://10.10.0.120:8023"
export WA_WIKIPEDIA="http://10.10.0.120:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export WA_MAP="http://10.10.0.120:3000"
export WA_HOMEPAGE="http://10.10.0.120:4399"


# Map WA_ variables to the names expected by browser_env
export SHOPPING=$WA_SHOPPING
export SHOPPING_ADMIN=$WA_SHOPPING_ADMIN
export REDDIT=$WA_REDDIT
export GITLAB=$WA_GITLAB
export WIKIPEDIA=$WA_WIKIPEDIA
export MAP=$WA_MAP
export HOMEPAGE=$WA_HOMEPAGE

export OPENAI_API_KEY=${OPENAI_API_KEY}

START_INDEX=0
END_INDEX=4

for site in "shopping" "wikipedia" "gitlab" "reddit" "map" 
do

  echo ""
  echo "=================================================="
  echo "🔄 Starting Benchmark for Site: $site ($START_INDEX ~ $END_INDEX)"
  echo "=================================================="

  DEST_DIR="results/$site"
  mkdir -p "$DEST_DIR"
  

  # python pipeline_baseline.py --website "$site"

  python pipeline_baseline.py --website "$site" --parallel 2 --start_index "$START_INDEX" --end_index "$END_INDEX"

  if ls results/webarena* 1> /dev/null 2>&1; then
      mv results/webarena* "$DEST_DIR/"
      echo "✅ Saved output directories to: $DEST_DIR/"
  else
      echo "⚠️  No tasks matched for '$site' in this range."
  fi

  sleep 1
done

echo ""
echo "=================================================="
echo "🎉 All Site Benchmarks Completed"
echo "=================================================="




# mkdir -p ./.auth
# python -m browser_env.auto_login
