export WA_SHOPPING="http://10.10.0.120:7770"
export WA_SHOPPING_ADMIN="http://10.10.0.120:7780/admin"
export WA_REDDIT="http://10.10.0.120:9999"
export WA_GITLAB="http://10.10.0.120:8023"
export WA_WIKIPEDIA="http://10.10.0.120:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export WA_MAP="http://10.10.0.120:3000"
export WA_HOMEPAGE="http://10.10.0.120:4399"
export OPENAI_API_KEY=${OPENAI_API_KEY}


for site in "map" #"shopping_admin" #  "gitlab" "reddit" "map" 
do
  echo ""
  echo "=================================================="
  echo "🔄 Starting Benchmark for Site: $site ($START_INDEX ~ $END_INDEX)"
  echo "=================================================="

  DEST_DIR="results/$site"
  mkdir -p "$DEST_DIR"

  python pipeline.py --website "$site" 

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