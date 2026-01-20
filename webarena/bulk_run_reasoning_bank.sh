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
export RETRIEVE_TYPE="bm25"

# START_INDEX=0
# END_INDEX=5


# SITES=("shopping_admin" "shopping" "wikipedia" "gitlab" "reddit" "map")

for site in "map" #"reddit" #"gitlab" #"wikipedia" #"map" #"shopping_admin" #
do

  echo ""
  echo "=================================================="
  echo "🔄 Starting Reasoning Bank Benchmark for Site: $site ($START_INDEX ~ $END_INDEX)"
  echo "=================================================="

  # python pipeline_reasoning_bank.py --website "$site"

  python pipeline_reasoning_bank.py --website "$site" --reasoning_bank_path "data/reasoning_bank.json" --retrieve_type "$RETRIEVE_TYPE" #--start_index "$START_INDEX" --end_index "$END_INDEX"

  sleep 1
done

echo ""
echo "=================================================="
echo "🎉 All Reasoning Bank Site Benchmarks Completed"
echo "=================================================="



# mkdir -p ./.auth
# python -m browser_env.auto_login