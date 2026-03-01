.PHONY: eval-dump eval-rubrics eval-rate eval-view eval-show eval-viewer eval-result-viewer

eval-dump:
	@test -n "$(VERSION)" || (echo "Error: Usage: make eval-dump VERSION=v1" && exit 1)
	uv run python eval/dump_traces.py --version $(VERSION)

eval-data-viewer:
	@test -n "$(VERSION)" || (echo "Error: Usage: make eval-data-viewer VERSION=v1" && exit 1)
	uv run python eval/launch_data_viewer.py --version $(VERSION)

eval-rubrics:
	@test -n "$(VERSION)" || (echo "Error: Usage: make eval-rubrics VERSION=v1" && exit 1)
	uv run python eval/gen_rubrics.py --version $(VERSION)

eval-rate:
	@test -n "$(VERSION)" || (echo "Error: Usage: make eval-rate VERSION=v1 PROMPT=eval/prompts/v2.txt" && exit 1)
	@test -n "$(PROMPT)" || (echo "Error: Usage: make eval-rate VERSION=v1 PROMPT=eval/prompts/v2.txt" && exit 1)
	uv run python eval/autorater.py --version $(VERSION) --prompt-file $(PROMPT) \
		$(if $(JUDGE_MODEL),--judge-model $(JUDGE_MODEL)) \
		$(if $(DRY_RUN),--dry-run)

eval-view:
	@test -n "$(VERSION)" || (echo "Error: Usage: make eval-view VERSION=v1" && exit 1)
	uv run python eval/view_traces.py --version $(VERSION)

eval-show:
	@test -n "$(VERSION)" || (echo "Error: Usage: make eval-show VERSION=v1 TRACE=<id-prefix>" && exit 1)
	@test -n "$(TRACE)" || (echo "Error: Usage: make eval-show VERSION=v1 TRACE=<id-prefix>" && exit 1)
	uv run python eval/view_traces.py --version $(VERSION) --trace-id $(TRACE)

eval-result-viewer:
	@test -n "$(RESULT)" || (echo "Error: Usage: make eval-result-viewer RESULT=eval/data/v2/results/run.json" && exit 1)
	uv run python eval/launch_result_viewer.py --result $(RESULT)
