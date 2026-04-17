"""this module defines the RESTful web service app for the project."""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    generate_latest,
)
from prometheus_client.multiprocess import MultiProcessCollector

from light_serve.serve.backends.base_backend import BaseLLMBackend
from light_serve.serve.factory.backend_factory import backend_factory
from light_serve.serve.openai.protocol import (
    ChatCompletionRequest,
    CompletionRequest,
    DetokenizeRequest,
    EmbeddingRequest,
    TokenizeChatRequest,
    TokenizeCompletionRequest,
)

# Global variables
serving_model: BaseLLMBackend = None
model_name: str = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the model at statup the service."""
    global serving_model, model_name  # noqa: F824

    # Retrieve runtime configs passed from `start_model`
    runtime_configs = app.state.runtime_configs
    model_config_dict = runtime_configs["model_config_dict"]

    # Update model config dict with runtime configurations
    model_config_dict.update(
        {
            "model_name": runtime_configs["model_name"],
            "backend": runtime_configs["backend"],
            "distributed_backend": runtime_configs["distributed_backend"],
            "disable_cuda_graph": runtime_configs["disable_cuda_graph"],
            "enforce_eager": runtime_configs["enforce_eager"],
            "reasoning_parser": runtime_configs["reasoning_parser"],
            "enable_auto_tool_choice": runtime_configs["enable_auto_tool_choice"],
            "tool_call_parser": runtime_configs["tool_call_parser"],
            "enable_prefix_caching": runtime_configs["enable_prefix_caching"],
            "trust_remote_code": runtime_configs["trust_remote_code"],
            "max_num_seqs": runtime_configs["max_num_seqs"],
            "is_embedding": runtime_configs["is_embedding"],
            "enable_expert_parallel": runtime_configs["enable_expert_parallel"],
            "pipeline_parallel_size": runtime_configs["pipeline_parallel_size"],
        }
    )

    print(f"Initializing model with config: {model_config_dict}")
    backend_class = backend_factory(runtime_configs["backend"])
    serving_model = backend_class(**model_config_dict)
    await serving_model.start_server_or_load_model()
    app.state.serving_model = serving_model  # Attach the backend to the app's state
    yield
    # Clean up resources if needed
    await serving_model.service_shutdown()
    print("Shutting down vllm_backend.")


app = FastAPI(lifespan=lifespan)


@app.on_event("startup")
async def initialize():
    """Initialize the model at statup the service."""
    pass


@app.get("/health")
async def health(self) -> Response:
    """Health check."""
    return Response(status_code=200)


@app.post("/v1/chat/completions", response_model=None)
async def create_chat_completion(request: ChatCompletionRequest, raw_request: Request):
    """Open AI Chat completions endpoint."""
    return await serving_model.chat_completion(request, raw_request)


@app.post("/v1/completions", response_model=None)
async def create_completion(request: CompletionRequest, raw_request: Request):
    """Open AI Chat completions endpoint."""
    return await serving_model.completion(request, raw_request)


@app.post("/tokenize_completion", response_model=None)
async def tokenize_completion(request: TokenizeCompletionRequest, raw_request: Request):
    """Tokenize completion endpoint."""
    return await serving_model.tokenize_completion(request, raw_request)


@app.post("/tokenize_chat", response_model=None)
async def tokenize_chat(request: TokenizeChatRequest, raw_request: Request):
    """Tokenize chat endpoint."""
    return await serving_model.tokenize_chat(request, raw_request)


@app.post("/detokenize", response_model=None)
async def detokenize(request: DetokenizeRequest, raw_request: Request):
    """Open AI embeddings endpoint."""
    return await serving_model.detokenize(request, raw_request)


@app.post("/v1/embeddings", response_model=None)
async def create_embedding(request: EmbeddingRequest, raw_request: Request):
    """Open AI embeddings endpoint."""
    return await serving_model.embedding(request, raw_request)


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint compatible with vLLM's exporter."""
    # Use multiprocess collector if PROMETHEUS_MULTIPROC_DIR is set (vLLM MP frontend)
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        MultiProcessCollector(registry)
        output = generate_latest(registry)
    else:
        output = generate_latest(REGISTRY)

    return Response(content=output, media_type=CONTENT_TYPE_LATEST)


@app.on_event("shutdown")
async def shutdown():
    """Stop the listener and backend when shutdown the service."""
    await serving_model.service_shutdown()
