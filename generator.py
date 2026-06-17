from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
from config import MODEL_NAME

# Load tokenizer and model
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

# Hugging Face pipeline using 'text-generation' task (compatible with older transformers)
pipe = pipeline(
    task="text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=100,
    do_sample=True,
    temperature=0.7,
    return_full_text=False
)

def generate_answer(query: str, context: str) -> str:
    """
    Generate an answer using Flan-T5 LLM with provided context.
    Bypasses the transformers pipeline for better control in this environment.
    """
    prompt = f"""
Answer the question based on the context provided.
Context: {context}
Question: {query}
Answer:"""
    # Tokenize input and move to same device as model
    device = model.device
    tokenizer.truncation_side = 'left'
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=768).to(device)
    num_tokens = inputs['input_ids'].shape[1]
    
    # Generate response
    outputs = model.generate(
        input_ids=inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
        max_new_tokens=150,
        min_new_tokens=5, # Force more than just a character
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        repetition_penalty=2.0,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id
    )
    
    # Decode and return
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    with open("generator_debug.txt", "a") as f:
        f.write(f"\n--- NEW QUERY ---\n")
        f.write(f"Prompt Sent to LLM (Context Length: {len(context)}, Tokens: {num_tokens})\n")
        f.write(f"{prompt}\n")
        f.write(f"Response from LLM\n")
        f.write(f"{response}\n")
        f.write(f"--- END QUERY ---\n")
    
    return response.strip()


def generate_answer_stream(query: str, context: str):
    """
    Generate an answer with streaming token-by-token output.
    Yields tokens as they are generated for SSE streaming.
    """
    prompt = f"""
Answer the question based on the context provided.
Context: {context}
Question: {query}
Answer:"""

    device = model.device
    tokenizer.truncation_side = 'left'
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=768).to(device)

    # Use streaming generation with text streamer
    from transformers import TextStreamer
    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    # Generate with streamer - this will yield tokens as they're produced
    model.generate(
        input_ids=inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
        max_new_tokens=150,
        min_new_tokens=5,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        repetition_penalty=2.0,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
        streamer=streamer
    )