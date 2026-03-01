.PHONY: eval-dump eval-rubrics eval-rate eval-view eval-show eval-viewer

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
	uv run python eval/autorater.py --version $(VERSION) --prompt-file $(PROMPT)

eval-view:
	@test -n "$(VERSION)" || (echo "Error: Usage: make eval-view VERSION=v1" && exit 1)
	uv run python eval/view_traces.py --version $(VERSION)

eval-show:
	@test -n "$(VERSION)" || (echo "Error: Usage: make eval-show VERSION=v1 TRACE=<id-prefix>" && exit 1)
	@test -n "$(TRACE)" || (echo "Error: Usage: make eval-show VERSION=v1 TRACE=<id-prefix>" && exit 1)
	uv run python eval/view_traces.py --version $(VERSION) --trace-id $(TRACE)
