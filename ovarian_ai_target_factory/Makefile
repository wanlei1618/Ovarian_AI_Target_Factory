.PHONY: init check-disk literature datasets report daily

init:
	python scripts/initialize_project.py

check-disk:
	python scripts/check_disk_usage.py

literature:
	python scripts/00_literature_watch/literature_watcher.py

datasets:
	python scripts/01_dataset_watch/dataset_watcher.py

report:
	python scripts/07_report/report_generator.py --mode daily

daily:
	python scripts/run_daily_pipeline.py
