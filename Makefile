.PHONY: eval-dump eval-rubrics eval-rate

eval-dump:
	uv run python eval/dump_traces.py

eval-rubrics:
	uv run python eval/gen_rubrics.py

eval-rate:
	@test -n "$(PROMPT)" || (echo "Error: Usage: make eval-rate PROMPT=eval/prompts/v2.txt" && exit 1)
	uv run python eval/autorater.py --prompt-file $(PROMPT)
