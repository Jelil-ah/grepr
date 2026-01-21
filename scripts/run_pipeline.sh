#!/bin/bash
# Grepr Pipeline Runner
# Usage: ./run_pipeline.sh [fetch|process|push|all|status]

cd "$(dirname "$0")/.."

case "$1" in
    fetch)
        echo "=== FETCHING POSTS ==="
        python3 fetch_only.py "${@:2}"
        ;;
    process)
        echo "=== PROCESSING WITH AI ==="
        python3 process_only.py "${@:2}"
        ;;
    push)
        echo "=== PUSHING TO DB ==="
        python3 push_only.py "${@:2}"
        ;;
    all)
        echo "=== FULL PIPELINE ==="
        python3 fetch_only.py --period "${2:-week}"
        python3 process_only.py
        python3 push_only.py
        ;;
    status)
        echo "=== STATUS ==="
        python3 scheduler.py status
        ;;
    *)
        echo "Usage: $0 [fetch|process|push|all|status]"
        echo ""
        echo "Commands:"
        echo "  fetch   - Fetch posts from Reddit"
        echo "  process - Process posts with AI (Groq/DeepSeek)"
        echo "  push    - Push processed posts to NocoDB"
        echo "  all     - Run full pipeline (fetch + process + push)"
        echo "  status  - Show scheduler status"
        echo ""
        echo "Examples:"
        echo "  $0 fetch --period week"
        echo "  $0 process --all-unprocessed"
        echo "  $0 push --all-unpushed"
        echo "  $0 all week"
        ;;
esac
