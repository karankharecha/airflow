#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

from airflow.exceptions import AirflowException
from airflow.providers.databricks.hooks.databricks import DatabricksHook, RunState


def normalise_json_content(content, json_path: str = "json") -> str | bool | list | dict:
    """
    Normalize content or all values of content if it is a dict to a string.

    The function will throw if content contains non-string or non-numeric non-boolean
    types. The reason why we have this function is because the ``self.json`` field
    must be a dict with only string values. This is because ``render_template`` will
    fail for numerical values.

    The only one exception is when we have boolean values, they can not be converted
    to string type because databricks does not understand 'True' or 'False' values.
    """
    normalise = normalise_json_content
    if isinstance(content, (str, bool)):
        return content
    if isinstance(content, (int, float)):
        # Databricks can tolerate either numeric or string types in the API backend.
        return str(content)
    if isinstance(content, (list, tuple)):
        return [normalise(e, f"{json_path}[{i}]") for i, e in enumerate(content)]
    if isinstance(content, dict):
        return {k: normalise(v, f"{json_path}[{k}]") for k, v in content.items()}
    param_type = type(content)
    msg = f"Type {param_type} used for parameter {json_path} is not a number or a string"
    raise AirflowException(msg)


def extract_failed_task_errors(
    hook: DatabricksHook, run_info: dict, run_state: RunState
) -> list[dict[str, str | int]]:
    """
    Extract error information from failed tasks in a Databricks run (synchronous version).

    :param hook: Databricks hook instance for making API calls
    :param run_info: Run information dictionary from Databricks API
    :param run_state: Run state object
    :return: List of failed task information with task_key, run_id, and error
    """
    failed_tasks = []
    if run_state.result_state == "FAILED":
        for task in run_info.get("tasks", []):
            if task.get("state", {}).get("result_state", "") == "FAILED":
                task_run_id = task["run_id"]
                task_key = task["task_key"]
                run_output = hook.get_run_output(task_run_id)
                if "error" in run_output:
                    error = run_output["error"]
                else:
                    error = run_state.state_message
                failed_tasks.append({"task_key": task_key, "run_id": task_run_id, "error": error})
    return failed_tasks


async def extract_failed_task_errors_async(
    hook: DatabricksHook, run_info: dict, run_state: RunState
) -> list[dict[str, str | int]]:
    """
    Extract error information from failed tasks in a Databricks run (asynchronous version).

    :param hook: Databricks hook instance for making API calls
    :param run_info: Run information dictionary from Databricks API
    :param run_state: Run state object
    :return: List of failed task information with task_key, run_id, and error
    """
    failed_tasks = []
    if run_state.result_state == "FAILED":
        for task in run_info.get("tasks", []):
            if task.get("state", {}).get("result_state", "") == "FAILED":
                task_run_id = task["run_id"]
                task_key = task["task_key"]
                run_output = await hook.a_get_run_output(task_run_id)
                if "error" in run_output:
                    error = run_output["error"]
                else:
                    error = run_state.state_message
                failed_tasks.append({"task_key": task_key, "run_id": task_run_id, "error": error})
    return failed_tasks


def validate_trigger_event(event: dict):
    """
    Validate correctness of the event received from DatabricksExecutionTrigger.

    See: :class:`~airflow.providers.databricks.triggers.databricks.DatabricksExecutionTrigger`.
    """
    keys_to_check = ["run_id", "run_page_url", "run_state", "errors"]
    for key in keys_to_check:
        if key not in event:
            raise AirflowException(f"Could not find `{key}` in the event: {event}")

    try:
        RunState.from_json(event["run_state"])
    except Exception:
        raise AirflowException(f"Run state returned by the Trigger is incorrect: {event['run_state']}")
