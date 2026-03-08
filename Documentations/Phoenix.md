# Phoenix Documentation

## Introduction

Phoenix is a monitoring and tracing tool by Arize. We use it to trace our agent's toolcalls and debug our code.

## Accessing Phoenix

You can access Phoenix by going to: [http://10.200.14.82:6007/](http://10.200.14.82:6007/) 

You will be promped to login with your username and password. 
The default username is `admin@localhost` and the password is `w_jkY7a.6EzmgfQ`.

## Installation

Install the following packages:

```bash
pip install arize-phoenix
```

## Setup

Run the following command, or set it in your .bashrc:

```bash
export OTEL_EXPORTER_OTLP_HEADERS='Authorization=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJBcGlLZXk6NCJ9.63j_N4wrKUZL4ZumPhqyM2svLifie-LwqFDqao7ZJrQ'
``` 

If Phoenix is not running, run:
```bash
PHOENIX_PORT=6007 PHOENIX_WORKING_DIR=/datapool/phoenix PHOENIX_ENABLE_AUTH=True PHOENIX_SECRET=testsecret000000000000000000000000000000 nohup phoenix serve > /var/log/phoenix.log &
```

The setup for phoenix can be found in `chatdku/chatdku/setup.py` with the function name `use_phoenix()`.

You can change the project name here:

https://github.com/Glitterccc/ChatDKU/blob/ee156832abf4d65e0dcac7456c71db4d717a085e/chatdku/chatdku/setup.py#L41


## Using Phoenix tracing

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
- **Last Updated**: 2026-03-08
- **Version**: 1.0.0 
- **Maintainers**: Temuulen  
- **Contact**: te100@duke.edu
