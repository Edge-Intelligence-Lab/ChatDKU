# Phoenix Documentation

## Introduction

Phoenix is a monitoring and tracing tool by Arize. We use it to trace our agent's toolcalls and debug our code.

## Accessing Phoenix

You can access Phoenix by going to: [http://10.200.14.82:6007/](http://10.200.14.82:6007/) 

You will be promped to login with your username and password. 
Ask the username and password from PM.

## Installation

Install the following packages:

```bash
pip install arize-phoenix
```

## Setup

Run the following command, or set it in your `~/.profile` (see `Env-variables.md`):

```bash
export OTEL_EXPORTER_OTLP_HEADERS=<API_KEY>
``` 

Ask the API_KEY from the PM.

If Phoenix is not running, run:
```bash
phoenix serve
```

The setup for phoenix can be found in `chatdku/chatdku/setup.py` with the function name `use_phoenix()`.

You can change the project name here:

https://github.com/Edge-Intelligence-Lab/ChatDKU/blob/ee156832abf4d65e0dcac7456c71db4d717a085e/chatdku/chatdku/setup.py#L41

## Using Phoenix Tracing

> [!IMPORTANT]
> Remember to run setup.py's use_phoenix() once before using the tracing.
> This is by default done in agent.py so you should not have to do it manually.

In our codebase, you will repeatedly see the following code:

```python
from chatdku.core.utils import span_ctx_start

with span_ctx_start("Name of the module", Type of the module) as span:
    span.set_attributes(
        {
            SpanAttributes.INPUT_VALUE: safe_json_dumps(
                dict(
                    inputs you would like to trace like:
                    key=value
                )
            ),
            SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
        }
    )

    do some computation

    span.set_attributes(
        {
            SpanAttributes.OUTPUT_VALUE: safe_json_dumps(
                dict(
                    outputs you would like to trace like:
                    key=value
                )
            ),
            SpanAttributes.OUTPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
        }
    )

```

This is like the basic use of how you can use opentelemetry to trace your code.
It is extremely useful for debugging and monitoring your module/tool.

You can find more information about tracing [here](https://arize.com/docs/ax/observe/tracing/setup/manual-instrumentation)
Also, the opentelemetry [docs](https://opentelemetry.io/docs/languages/python/instrumentation/)

---
- **Last Updated**: 2026-03-16
- **Maintainers**: Temuulen  
- **Contact**: te100@duke.edu
