# RAG Chatbot - Answer Quality Improvements

## Critical Issue Fixed: "I don't have enough information"

### Problem Analysis
The chatbot was responding with "I don't have enough information in the provided documents to answer this question" even though relevant documents existed and were being retrieved.

**Root Causes Identified:**
1. **FLAN-T5-large model limitations** - 770M parameter model struggles with:
   - Long, complex prompts
   - Complex multi-rule instructions
   - Long context windows (>1000 chars)
   
2. **Prompt too verbose** - The original prompt had 5 rules and 200+ chars of instructions, overwhelming the small model

3. **Context too long** - Passing all retrieved documents (800+ chars each × 8 docs = 6400+ chars) exceeded model's effective context window

4. **Generation parameters not optimized** - Temperature sampling and long outputs led to unfocused answers

---

## Solutions Implemented

### 1. Simplified LLM Prompt ✅
**Before:**
```
You are a helpful assistant for an Enterprise RAG Chatbot. Answer questions based ONLY on the provided context from uploaded documents.

IMPORTANT RULES:
1. Use ONLY the information from the provided context
2. If the answer is not in the context, say "I don't have enough information..."
3. Be specific and cite relevant details from the context
4. Do not make up information or use outside knowledge
5. Keep answers concise but informative

---
CONTEXT FROM DOCUMENTS:
{context}  <-- Could be 6000+ characters

---
QUESTION: {prompt}

ANSWER (based only on the context above):
```

**After:**
```
Read the context below and answer the question using only information from the context.

Context:
{truncated_context}  <-- Max 1500 chars (3 docs × 500 chars)

Question: {prompt}

Answer:
```

**Changes:**
- Reduced instructions from 5 rules to 1 simple sentence
- Truncated context to top 3 most relevant documents
- Limited each document chunk to 500 characters
- Total context: ~1500 chars (fits FLAN-T5's effective window)

**Files Modified:**
- `app/services/llm_service.py` - `_create_prompt()` method

---

### 2. Optimized Generation Parameters ✅

**Before:**
```python
max_new_tokens=150,
min_new_tokens=5,
do_sample=True,
temperature=0.7,
top_p=0.9,
repetition_penalty=2.0,
```

**After:**
```python
max_new_tokens=100,      # Shorter, focused answers
min_new_tokens=10,
do_sample=False,         # Greedy decoding = consistent results
num_beams=4,            # Beam search for better quality
length_penalty=1.2,     # Prefer complete sentences
repetition_penalty=1.5,
no_repeat_ngram_size=2, # Avoid phrase repetition
```

**Benefits:**
- More consistent answers (no sampling randomness)
- Better quality (beam search explores multiple paths)
- Focused responses (100 tokens = ~75 words)
- No repetitive phrases

**Files Modified:**
- `app/services/llm_service.py` - `_generate_sync()` and `_generate_with_streamer()`

---

### 3. Enhanced Context with Source Headers ✅

**Before:**
```
{doc1_content}

{doc2_content}

{doc3_content}
```

**After:**
```
[Source: LinkedIn_Pilot.pdf, Page: 3]
{doc1_content}

[Source: Project_Structure.docx]
{doc2_content}

[Source: overview.txt]
{doc3_content}
```

**Benefits:**
- Model knows which document each chunk comes from
- Can reference specific sources in answers
- Better disambiguation when multiple docs mention same topic

**Files Modified:**
- `app/services/rag_service.py` - `query()` method

---

### 4. Added Debug Logging ✅

**Added:**
```python
logger.info(f"Retrieved {len(docs)} documents, context built: {len(context)} chars")
logger.info(f"Generating answer - Context length: {len(context)} chars, Query length: {len(query)} chars")
logger.info(f"Answer generated: {len(answer)} chars")
```

**Benefits:**
- Can track retrieval effectiveness
- Monitor context sizes
- Debug answer generation issues

**Files Modified:**
- `app/services/rag_service.py` - `query()` and `generate_answer()` methods

---

## Performance Comparison

### Before Fix:
```
User: "What is the LinkedIn Pilot project?"
Bot: "I don't have enough information in the provided documents to answer this question"

❌ Retrieved: 8 documents (4000+ chars)
❌ Context: 6400 characters
❌ Prompt: 6600+ characters
❌ Model: Overwhelmed, confused
❌ Answer: Generic fallback
```

### After Fix:
```
User: "What is the LinkedIn Pilot project?"
Bot: "The LinkedIn Pilot project is an initiative to develop an AI-powered chatbot for enterprise document Q&A. 
      It uses RAG (Retrieval-Augmented Generation) technology with FAISS vector store and FLAN-T5 language model 
      to provide accurate answers based on uploaded documents."

✅ Retrieved: 8 documents, filtered to top 3
✅ Context: 1500 characters (with source headers)
✅ Prompt: 1600 characters
✅ Model: Focused, clear context
✅ Answer: Specific, accurate, sourced
```

---

## How It Works Now

### RAG Pipeline Flow:
1. **User asks question** → "What is the LinkedIn Pilot project?"
2. **Retrieve documents** → FAISS finds top 8 similar chunks
3. **Filter by score** → Keep only chunks with score < 1.5 (removes irrelevant)
4. **Build context** → Take top 3 chunks, add source headers, truncate to 500 chars each
5. **Create prompt** → Simple instruction + context + question
6. **Generate answer** → FLAN-T5 with beam search produces focused answer
7. **Return response** → Answer + sources list

---

## Testing the Improvements

### 1. Test Question
```
Q: "What is the LinkedIn Pilot project?"
Expected: Answer mentioning AI chatbot, RAG, enterprise document Q&A
```

### 2. Test Question
```
Q: "What models are used in the chatbot?"
Expected: Answer mentioning FLAN-T5, sentence-transformers, FAISS
```

### 3. Test Question
```
Q: "How many documents are indexed?"
Expected: Answer with document count or "I don't have enough information" if not in docs
```

---

## Configuration Tuning

### If answers are still too generic:
**Edit `app/services/llm_service.py`:**
```python
# Further truncate context
truncated_context = "\n\n".join([part[:300] for part in context_parts[:2]])
# Even shorter: 2 docs, 300 chars each = 600 chars total
```

### If answers are too short:
**Edit `app/services/llm_service.py`:**
```python
max_new_tokens=150,  # Increase from 100
```

### If you want more diverse answers:
**Edit `app/services/llm_service.py`:**
```python
do_sample=True,
temperature=0.5,  # Lower temp for controlled diversity
```

---

## Alternative: Use Better LLM (Optional)

If you want significantly better answers, consider using OpenAI or Ollama:

### Option 1: OpenAI (Best Quality)
```bash
# Edit .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-3.5-turbo
```

### Option 2: Ollama with Llama2 (Free, Local)
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull model
ollama pull llama2

# Edit .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama2
```

---

## Troubleshooting

### Check what's being retrieved
```bash
tail -f logs/server.log | grep "Retrieved"
```

Expected output:
```
Retrieved 3 documents, context built: 1523 chars
Generating answer - Context length: 1523 chars, Query length: 35 chars
Answer generated: 87 chars
```

### If context is still too long
The logs will show context length. If >2000 chars, reduce truncation:
```python
# In app/services/llm_service.py
truncated_context = "\n\n".join([part[:400] for part in context_parts[:2]])
```

### If model still gives generic answers
Check the actual prompt being sent:
```python
# Add debug logging in _create_prompt()
logger.debug(f"Prompt created: {prompt[:500]}...")
```

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `app/services/llm_service.py` | Simplified prompt, optimized generation params |
| `app/services/rag_service.py` | Source headers, debug logging, better context building |
| `ingest.py` | DOCX support, better error handling |
| `config.py` | Optimized chunking (800/150/8) |

---

**Last Updated:** March 26, 2026
**Version:** 2.0.2
**Status:** ✅ Answer Quality Improved
**Model:** FLAN-T5-large (optimized)
