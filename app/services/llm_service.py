"""
LLM service with multi-provider support (Local, OpenAI, Ollama)
"""
from typing import AsyncGenerator, Optional, Dict, Any
from abc import ABC, abstractmethod
from app.core.config import settings
from app.core.logging import get_logger
import asyncio

logger = get_logger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, context: str) -> str:
        """Generate a response."""
        pass
    
    @abstractmethod
    async def generate_stream(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        pass


class LocalLLMProvider(BaseLLMProvider):
    """Local LLM provider using Hugging Face models."""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._initialized = False
    
    def _initialize(self):
        """Lazy initialization of model and tokenizer."""
        if self._initialized:
            return
        
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        
        logger.info(f"Loading local LLM model: {settings.MODEL_NAME}")
        self.tokenizer = AutoTokenizer.from_pretrained(settings.MODEL_NAME)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(settings.MODEL_NAME)
        self._initialized = True
    
    async def generate(self, prompt: str, context: str) -> str:
        """Generate response using local model."""
        self._initialize()
        
        full_prompt = self._create_prompt(prompt, context)
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self._generate_sync,
            full_prompt
        )
        
        # Clean up common hallucinations
        response = response.replace('__pycache__/', '')
        response = response.replace('__pycache__', '')
        response = response.replace('.pkl', '')
        response = response.replace('index.pkl', '')
        
        return response
    
    async def generate_stream(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate streaming response using local model."""
        self._initialize()
        
        full_prompt = self._create_prompt(prompt, context)
        
        from transformers import TextStreamer
        import queue
        
        token_queue = queue.Queue()
        done_event = asyncio.Event()
        
        def run_generation():
            try:
                class QueueStreamer(TextStreamer):
                    def put(self, token):
                        if token is not None:
                            token_queue.put_nowait(token)
                
                streamer = QueueStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
                self._generate_with_streamer(full_prompt, streamer)
            finally:
                token_queue.put(None)  # Sentinel value
        
        # Run generation in background thread
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, run_generation)
        
        # Yield tokens as they arrive
        while True:
            try:
                token = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, token_queue.get),
                    timeout=30.0
                )
                if token is None:
                    break
                yield token
            except asyncio.TimeoutError:
                break
    
    def _create_prompt(self, prompt: str, context: str) -> str:
        """Create the full prompt with context - optimized for FLAN-T5."""
        # FLAN-T5 works better with simple, direct prompts
        # Truncate context to avoid overwhelming the model (max 500 chars per doc, 3 docs)
        context_parts = context.split("\n\n")
        truncated_context = "\n\n".join([part[:500] for part in context_parts[:3]])
        
        return f"""Read the context below and answer the question using only information from the context.

Context:
{truncated_context}

Question: {prompt}

Answer:"""
    
    def _generate_sync(self, prompt: str) -> str:
        """Synchronous generation for local model."""
        from transformers import AutoModelForSeq2SeqLM

        device = self.model.device
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512  # Reduced to fit model's sweet spot
        ).to(device)

        outputs = self.model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=100,  # Shorter, more focused answers
            min_new_tokens=10,
            do_sample=False,  # Greedy decoding for more consistent results
            num_beams=4,  # Beam search for better quality
            length_penalty=1.2,  # Prefer longer (but not too long) answers
            repetition_penalty=1.5,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            no_repeat_ngram_size=2,  # Avoid repeating phrases
        )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response.strip()
    
    def _generate_with_streamer(self, prompt: str, streamer):
        """Synchronous generation with streaming."""
        device = self.model.device
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512
        ).to(device)

        self.model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=100,
            min_new_tokens=10,
            do_sample=False,
            num_beams=4,
            length_penalty=1.2,
            repetition_penalty=1.5,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            no_repeat_ngram_size=2,
            streamer=streamer
        )


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI LLM provider."""
    
    def __init__(self):
        self.client = None
        self._initialized = False
    
    def _initialize(self):
        """Initialize OpenAI client."""
        if self._initialized:
            return
        
        from openai import AsyncOpenAI
        
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._initialized = True
    
    async def generate(self, prompt: str, context: str) -> str:
        """Generate response using OpenAI."""
        self._initialize()
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {prompt}"}
        ]
        
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    
    async def generate_stream(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate streaming response using OpenAI."""
        self._initialize()
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {prompt}"}
        ]
        
        stream = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OllamaLLMProvider(BaseLLMProvider):
    """Ollama LLM provider for local models."""

    def __init__(self):
        self.client = None
        self._initialized = False

    def _initialize(self):
        """Initialize Ollama client."""
        if self._initialized:
            return

        import ollama
        self.client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
        self._initialized = True

    async def generate(self, prompt: str, context: str) -> str:
        """Generate response using Ollama."""
        self._initialize()

        full_prompt = f"""Answer the question based on the context provided.
Context: {context}
Question: {prompt}
Answer:"""

        response = await self.client.generate(
            model=settings.OLLAMA_MODEL,
            prompt=full_prompt,
            options={"temperature": 0.7, "num_predict": 500}
        )

        return response["response"]

    async def generate_stream(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate streaming response using Ollama."""
        self._initialize()

        full_prompt = f"""Answer the question based on the context provided.
Context: {context}
Question: {prompt}
Answer:"""

        response = await self.client.generate(
            model=settings.OLLAMA_MODEL,
            prompt=full_prompt,
            options={"temperature": 0.7, "num_predict": 500},
            stream=True
        )

        async for chunk in response:
            yield chunk["response"]


class VLLMProvider(BaseLLMProvider):
    """
    vLLM provider for high-performance local inference.
    
    vLLM provides 10x faster inference than standard transformers
    with continuous batching and PagedAttention.
    
    Setup:
        pip install vllm
        python -m vllm.entrypoints.api_server --model mistralai/Mistral-7B-Instruct-v0.2
    """

    def __init__(self):
        self.client = None
        self._initialized = False

    def _initialize(self):
        """Initialize vLLM client."""
        if self._initialized:
            return

        try:
            from openai import AsyncOpenAI
            # vLLM uses OpenAI-compatible API
            self.client = AsyncOpenAI(
                api_key="vllm",  # vLLM doesn't require a real API key
                base_url=settings.VLLM_BASE_URL
            )
            self._initialized = True
            logger.info(f"vLLM provider initialized at {settings.VLLM_BASE_URL}")
        except ImportError:
            logger.error("vLLM not installed. Run: pip install vllm")
            raise

    async def generate(self, prompt: str, context: str) -> str:
        """Generate response using vLLM."""
        self._initialize()

        full_prompt = self._create_prompt(prompt, context)

        response = await self.client.chat.completions.create(
            model=settings.VLLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            top_p=0.9,
        )

        return response.choices[0].message.content

    async def generate_stream(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate streaming response using vLLM."""
        self._initialize()

        full_prompt = self._create_prompt(prompt, context)

        response = await self.client.chat.completions.create(
            model=settings.VLLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            top_p=0.9,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _create_prompt(self, prompt: str, context: str) -> str:
        """Create prompt optimized for instruction-tuned models."""
        # Truncate context for longer models
        context_parts = context.split("\n\n")
        truncated_context = "\n\n".join([part[:800] for part in context_parts[:5]])

        return f"""You are a helpful assistant. Answer the question using only the information from the provided context.

Context:
{truncated_context}

Question: {prompt}

Answer:"""


class GroqLLMProvider(BaseLLMProvider):
    """
    Groq provider for ultra-fast LLM inference.
    
    Groq LPU provides the fastest inference speeds (500+ tokens/sec)
    with models like Llama-3-70B, Mixtral-8x7B.
    
    Setup:
        - Get API key from https://console.groq.com
        - Set GROQ_API_KEY in environment
    """

    def __init__(self):
        self.client = None
        self._initialized = False

    def _initialize(self):
        """Initialize Groq client."""
        if self._initialized:
            return

        try:
            from groq import AsyncGroq
            
            if not settings.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY not configured")
            
            self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            self._initialized = True
            logger.info(f"Groq provider initialized with model: {settings.GROQ_MODEL}")
        except ImportError:
            logger.error("Groq not installed. Run: pip install groq")
            raise

    async def generate(self, prompt: str, context: str) -> str:
        """Generate response using Groq."""
        self._initialize()

        full_prompt = self._create_prompt(prompt, context)

        response = await self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context. Be concise and accurate."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            top_p=0.9,
        )

        return response.choices[0].message.content

    async def generate_stream(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate streaming response using Groq."""
        self._initialize()

        full_prompt = self._create_prompt(prompt, context)

        response = await self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context. Be concise and accurate."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            top_p=0.9,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _create_prompt(self, prompt: str, context: str) -> str:
        """Create prompt optimized for Groq models."""
        # Groq models can handle longer contexts
        context_parts = context.split("\n\n")
        truncated_context = "\n\n".join([part[:1000] for part in context_parts[:6]])

        return f"""You are a helpful assistant. Answer the question using only the information from the provided context.

Context:
{truncated_context}

Question: {prompt}

Answer:"""


class TogetherLLMProvider(BaseLLMProvider):
    """
    Together AI provider for cloud-based LLM inference.
    
    Together AI provides access to various open-source models
    with fast inference and competitive pricing.
    
    Setup:
        - Get API key from https://together.ai
        - Set TOGETHER_API_KEY in environment
    """

    def __init__(self):
        self.client = None
        self._initialized = False

    def _initialize(self):
        """Initialize Together client."""
        if self._initialized:
            return

        try:
            from together import Together
            
            if not settings.TOGETHER_API_KEY:
                raise ValueError("TOGETHER_API_KEY not configured")
            
            self.client = Together(api_key=settings.TOGETHER_API_KEY)
            self._initialized = True
            logger.info(f"Together provider initialized with model: {settings.TOGETHER_MODEL}")
        except ImportError:
            logger.error("Together AI not installed. Run: pip install together")
            raise

    async def generate(self, prompt: str, context: str) -> str:
        """Generate response using Together AI."""
        self._initialize()

        full_prompt = self._create_prompt(prompt, context)

        response = await self.client.chat.completions.create(
            model=settings.TOGETHER_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            top_p=0.9,
        )

        return response.choices[0].message.content

    async def generate_stream(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Generate streaming response using Together AI."""
        self._initialize()

        full_prompt = self._create_prompt(prompt, context)

        response = await self.client.chat.completions.create(
            model=settings.TOGETHER_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            top_p=0.9,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _create_prompt(self, prompt: str, context: str) -> str:
        """Create prompt optimized for Together models."""
        context_parts = context.split("\n\n")
        truncated_context = "\n\n".join([part[:800] for part in context_parts[:5]])

        return f"""You are a helpful assistant. Answer the question using only the information from the provided context.

Context:
{truncated_context}

Question: {prompt}

Answer:"""


class LLMService:
    """Main LLM service that routes to appropriate provider."""

    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
        self.current_provider: Optional[str] = None
        self._initialized = False

    def initialize(self, provider: str = None):
        """Initialize LLM providers."""
        if self._initialized:
            return

        provider = provider or settings.LLM_PROVIDER

        # Initialize requested provider
        if provider == "local":
            self.providers["local"] = LocalLLMProvider()
            self.current_provider = "local"
        elif provider == "openai":
            self.providers["openai"] = OpenAILLMProvider()
            self.current_provider = "openai"
        elif provider == "ollama":
            self.providers["ollama"] = OllamaLLMProvider()
            self.current_provider = "ollama"
        elif provider == "vllm":
            self.providers["vllm"] = VLLMProvider()
            self.current_provider = "vllm"
        elif provider == "groq":
            self.providers["groq"] = GroqLLMProvider()
            self.current_provider = "groq"
        elif provider == "together":
            self.providers["together"] = TogetherLLMProvider()
            self.current_provider = "together"
        else:
            # Default to local
            self.providers["local"] = LocalLLMProvider()
            self.current_provider = "local"

        self._initialized = True
        logger.info(f"LLM Service initialized with provider: {self.current_provider}")

    async def generate(self, prompt: str, context: str, provider: Optional[str] = None) -> str:
        """Generate a response using the specified or default provider."""
        if not self._initialized:
            self.initialize()

        provider = provider or self.current_provider

        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")

        llm = self.providers[provider]
        return await llm.generate(prompt, context)

    async def generate_stream(
        self,
        prompt: str,
        context: str,
        provider: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        if not self._initialized:
            self.initialize()

        provider = provider or self.current_provider

        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")

        llm = self.providers[provider]
        async for token in llm.generate_stream(prompt, context):
            yield token

    def switch_provider(self, provider: str):
        """Switch to a different provider."""
        if provider not in self.providers:
            # Try to initialize the new provider
            if provider == "local":
                self.providers["local"] = LocalLLMProvider()
            elif provider == "openai":
                self.providers["openai"] = OpenAILLMProvider()
            elif provider == "ollama":
                self.providers["ollama"] = OllamaLLMProvider()
            elif provider == "vllm":
                self.providers["vllm"] = VLLMProvider()
            elif provider == "groq":
                self.providers["groq"] = GroqLLMProvider()
            elif provider == "together":
                self.providers["together"] = TogetherLLMProvider()
            else:
                raise ValueError(f"Unsupported provider: {provider}")

        self.current_provider = provider
        logger.info(f"Switched LLM provider to: {provider}")


# Global LLM service instance
llm_service = LLMService()


def get_llm_service() -> LLMService:
    """Get the LLM service instance."""
    return llm_service
