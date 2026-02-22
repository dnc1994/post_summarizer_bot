.PHONY: eval-dump eval-rubrics eval-rate eval-view eval-show

eval-dump:
	uv run python eval/dump_traces.py

eval-rubrics:
	uv run python eval/gen_rubrics.py

eval-rate:
	@test -n "$(PROMPT)" || (echo "Error: Usage: make eval-rate PROMPT=eval/prompts/v2.txt" && exit 1)
	uv run python eval/autorater.py --prompt-file $(PROMPT)

eval-view:
	uv run python eval/view_traces.py

eval-show:
	@test -n "$(TRACE)" || (echo "Error: Usage: make eval-show TRACE=<trace-id-prefix>" && exit 1)
	uv run python eval/view_traces.py --trace-id $(TRACE)
