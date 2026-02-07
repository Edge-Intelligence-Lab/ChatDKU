import os

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from phoenix.otel import register

from chatdku.config import config


def mydeepcopy(self, memo):
    return self


def setup(add_system_prompt: bool = False, use_llm: bool = True) -> None:
    """Setup common resources from command line arguments."""
    pass


def use_phoenix():
    phoenix_port = os.environ.get("PHOENIX_PORT", 6007)
    collector_endpoint = f"http://127.0.0.1:{phoenix_port}/v1/traces"
    tracer_provider = register(
        project_name="default",  # Default is 'default'
        auto_instrument=True,  # See 'Trace all calls made to a library' below
        endpoint=collector_endpoint,
        batch=True,
    )
    config.tracer = tracer_provider.get_tracer(__name__)
    span_exporter = OTLPSpanExporter(endpoint=collector_endpoint)
    simple_span_processor = SimpleSpanProcessor(span_exporter=span_exporter)
    tracer_provider.add_span_processor(simple_span_processor)
