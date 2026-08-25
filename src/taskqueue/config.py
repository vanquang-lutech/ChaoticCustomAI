"""Task names and modules imported by the Celery worker.

Names stay string constants and the modules are imported by path: the services enqueue work by
name and never import the task modules, which is what keeps services and workers free of an
import cycle.
"""

TASK_REMOVE_BACKGROUND = "chaotic.remove_background"
TASK_GENERATE_IMAGE = "chaotic.generate_image"
TASK_CUSTOM_TEXT = "chaotic.custom_text"

TASK_MODULES = [
    "src.workers.tasks.remove_background",
    "src.workers.tasks.generate_image",
    "src.workers.tasks.custom_text",
]
