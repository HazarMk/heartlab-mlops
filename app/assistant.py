"""Source-grounded information assistant, kept separate from patient records."""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

import httpx
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer

from app.portal import require_roles

router = APIRouter(prefix="/assistant", tags=["health information assistant"])
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://qwen:8080").rstrip("/")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5-0.5b")

# Curated starter knowledge. This is a project FAQ and safety guidance, not a
# clinical reference database. Medical content must be reviewed before expansion.
KNOWLEDGE = [
    {
        "id": "appointments-fr", "title": "Rendez-vous HeartLab", "language": "fr",
        "text": "Pour demander un rendez-vous, ouvrez l'onglet Rendez-vous, choisissez un professionnel et une date future, puis envoyez la demande. Elle reste en attente jusqu'à la réponse du cabinet. L'historique affiche vos demandes précédentes. Cette démonstration n'envoie pas de SMS.",
        "source": "Guide local HeartLab — rendez-vous", "url": None,
    },
    {
        "id": "appointments-en", "title": "HeartLab appointments", "language": "en",
        "text": "To request an appointment, open the Appointments tab, choose a clinician and a future date, then submit the request. It remains pending until the clinic responds. The History tab shows previous requests. This demo does not send SMS messages.",
        "source": "HeartLab local guide — appointments", "url": None,
    },
    {
        "id": "privacy-fr", "title": "Confidentialité et fiche santé", "language": "fr",
        "text": "N'entrez pas de nom complet, numéro de téléphone, numéro CNAM ni détail médical personnel dans l'assistant. La question peut être envoyée à un fournisseur externe uniquement si vous activez explicitement le mode IA. L'assistant ne lit pas votre fiche santé ou vos rendez-vous.",
        "source": "Guide local HeartLab — confidentialité", "url": None,
    },
    {
        "id": "privacy-en", "title": "Privacy and health profile", "language": "en",
        "text": "Do not enter your full name, phone number, CNAM number, or personal medical details in the assistant. Your question is sent to the external AI provider only if you explicitly enable that option. The assistant does not access your health profile or appointments.",
        "source": "HeartLab local guide — privacy", "url": None,
    },
    {
        "id": "scope-fr", "title": "Limites de l'assistant", "language": "fr",
        "text": "L'assistant fournit des informations générales à partir des sources affichées. Il ne diagnostique pas, ne prescrit pas de médicament, n'interprète pas un dossier individuel et ne remplace pas un professionnel de santé. Si les sources ne répondent pas, il doit le dire.",
        "source": "Règles de sécurité HeartLab", "url": None,
    },
    {
        "id": "scope-en", "title": "Assistant limitations", "language": "en",
        "text": "The assistant provides general information from the displayed sources only. It does not diagnose, prescribe medication, interpret individual medical records, or replace a healthcare professional. It should say when the sources do not answer a question.",
        "source": "HeartLab safety rules", "url": None,
    },
    {
        "id": "urgent-fr", "title": "Symptômes urgents", "language": "fr",
        "text": "Une douleur thoracique soudaine ou intense, une difficulté importante à respirer, une perte de connaissance ou une aggravation rapide nécessitent une aide médicale urgente. Contactez les services d'urgence locaux ou rendez-vous au service d'urgence le plus proche. N'attendez pas la réponse d'un assistant en ligne.",
        "source": "Organisation mondiale de la Santé — maladies cardiovasculaires", "url": "https://www.who.int/news-room/fact-sheets/detail/cardiovascular-diseases-(cvds)",
    },
    {
        "id": "urgent-en", "title": "Urgent symptoms", "language": "en",
        "text": "Sudden or severe chest pain, major difficulty breathing, loss of consciousness, or rapidly worsening symptoms require urgent medical help. Contact local emergency services or go to the nearest emergency department. Do not wait for an online assistant's reply.",
        "source": "World Health Organization — cardiovascular diseases", "url": "https://www.who.int/news-room/fact-sheets/detail/cardiovascular-diseases-(cvds)",
    },
    {
        "id": "appointments-ar", "title": "المواعيد في HeartLab", "language": "ar",
        "text": "لطلب موعد، افتح قسم المواعيد واختر الطبيب وتاريخاً مستقبلياً ثم أرسل الطلب. يبقى الطلب قيد الانتظار إلى أن يجيب الطبيب أو العيادة. يعرض قسم السجل الطلبات السابقة. هذه النسخة التجريبية لا ترسل رسائل SMS.",
        "source": "دليل HeartLab المحلي — المواعيد", "url": None,
    },
    {
        "id": "privacy-ar", "title": "الخصوصية والبيانات الصحية", "language": "ar",
        "text": "لا تكتب اسمك الكامل أو رقم هاتفك أو رقم CNAM أو تفاصيل طبية شخصية في المساعد. لا تُرسل سؤالك إلى مزود الذكاء الاصطناعي الخارجي إلا إذا فعّلت هذا الخيار بنفسك. لا يطّلع المساعد على ملفك الصحي أو مواعيدك.",
        "source": "دليل HeartLab المحلي — الخصوصية", "url": None,
    },
    {
        "id": "scope-ar", "title": "حدود المساعد الصحي", "language": "ar",
        "text": "يقدم المساعد معلومات عامة من المصادر المعروضة فقط. لا يشخّص المرض ولا يصف الأدوية ولا يفسر ملفاً طبياً فردياً ولا يعوض الطبيب. إذا لم تتضمن المصادر جواباً، يجب أن يوضح ذلك.",
        "source": "قواعد السلامة في HeartLab", "url": None,
    },
    {
        "id": "urgent-ar", "title": "متى تطلب المساعدة العاجلة", "language": "ar",
        "text": "ألم الصدر المفاجئ أو الشديد، أو صعوبة التنفس الشديدة، أو فقدان الوعي، أو تدهور الأعراض بسرعة تتطلب مساعدة طبية عاجلة. اتصل بخدمات الطوارئ المحلية أو توجه إلى أقرب قسم استعجالي. لا تنتظر إجابة مساعد عبر الإنترنت.",
        "source": "منظمة الصحة العالمية — أمراض القلب والأوعية الدموية", "url": "https://www.who.int/news-room/fact-sheets/detail/cardiovascular-diseases-(cvds)",
    },
]


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", value).casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


_VECTORIZER = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1)
_MATRIX = _VECTORIZER.fit_transform([_normalize(item["title"] + " " + item["text"]) for item in KNOWLEDGE])


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1200)
    use_llm: bool = False


def retrieve(question: str, limit: int = 3) -> list[dict[str, Any]]:
    query = _VECTORIZER.transform([_normalize(question)])
    scores = np.asarray((query @ _MATRIX.T).toarray()).ravel()
    indices = np.argsort(scores)[::-1][:limit]
    if not len(indices) or scores[indices[0]] < 0.035:
        return []
    return [{**KNOWLEDGE[int(i)], "score": float(scores[i])} for i in indices if scores[i] >= 0.02]


def _language(text: str) -> str:
    if any("\u0600" <= char <= "\u06ff" for char in text):
        return "ar"
    words = set(_normalize(text).split())
    english_markers = {"the", "is", "are", "what", "how", "when", "where", "can", "my", "today", "appointment", "please", "and", "with", "for"}
    french_markers = {"le", "la", "les", "est", "sont", "que", "comment", "quand", "ou", "mon", "mes", "aujourd", "rendez", "vous", "pour", "avec", "des", "une", "un"}
    en_score = len(words & english_markers)
    fr_score = len(words & french_markers)
    return "en" if en_score > fr_score else "fr"


def _document_answer(sources: list[dict[str, Any]], language: str) -> str:
    if not sources:
        if language == "ar":
            return "لا أجد جواباً موثوقاً في المصادر المتاحة. اسأل مختصاً صحياً."
        if language == "en":
            return "I could not find a supported answer in the available sources. Please ask a healthcare professional."
        return "Je ne trouve pas de réponse étayée dans les sources disponibles. Demandez conseil à un professionnel de santé."
    intro = {"ar": "المعلومات المتاحة في المصادر:", "en": "Here is the information available in the sources:", "fr": "Voici les informations présentes dans les sources :"}[language]
    return intro + "\n\n" + "\n\n".join(item["text"] for item in sources)


def _response_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts = [content["text"] for item in payload.get("output", []) for content in item.get("content", []) if content.get("type") == "output_text" and isinstance(content.get("text"), str)]
    return "\n".join(parts).strip()


async def _generate_with_llm(question: str, sources: list[dict[str, Any]]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    context = "\n\n".join(f"[{item['title']}] {item['text']}" for item in sources)
    instructions = (
        "You are HeartLab's informational assistant. Understand and answer in French, English, or Arabic. "
        "Use the same language as the user's question (for mixed-language questions, prefer the dominant language; Arabic script means Arabic). "
        "Use only the supplied retrieved passages. "
        "If they do not answer the question, say so and do not guess. Never diagnose, recommend treatment or medication, "
        "interpret personal medical records, or claim to be a doctor. For urgent symptoms, advise immediate contact with local emergency services."
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=1.5)) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "instructions": instructions, "input": f"Retrieved passages:\n{context}\n\nUser question:\n{question}", "store": False, "max_output_tokens": 250},
            )
        response.raise_for_status()
        answer = _response_text(response.json())
        if not answer:
            raise ValueError("No response text")
        return answer
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Le service IA est momentanément indisponible. Réessayez ou désactivez le mode IA.") from exc


async def _local_model_ready() -> bool:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(1.5, connect=0.8)) as client:
            response = await client.get(f"{LOCAL_LLM_URL}/health")
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


async def _generate_with_local_model(question: str, sources: list[dict[str, Any]]) -> str:
    context = "\n\n".join(f"[{item['title']}] {item['text']}" for item in sources)
    instructions = (
        "You are HeartLab's informational assistant. Understand and answer in French, English, or Arabic. "
        "Use the same language as the user's question; use Arabic if the question is written in Arabic script. "
        "Use only the supplied retrieved passages. If they do not answer, say so. Never diagnose, prescribe, "
        "interpret a personal medical record, or claim to be a doctor. For urgent symptoms, tell the user to contact local emergency services."
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=1.5)) as client:
            response = await client.post(
                f"{LOCAL_LLM_URL}/v1/chat/completions",
                json={
                    "model": LOCAL_LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": f"Retrieved passages:\n{context}\n\nUser question:\n{question}"},
                    ],
                    "stream": False,
                    "max_tokens": 220,
                    "temperature": 0.2,
                },
            )
        response.raise_for_status()
        answer = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not answer:
            raise ValueError("No response text")
        return answer
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Le modèle local n’est pas prêt ou met trop de temps. Les sources locales restent disponibles.") from exc


@router.get("/status")
async def assistant_status(_user: dict = Depends(require_roles("patient", "doctor"))):
    local_ready = await _local_model_ready()
    openai_enabled = bool(os.getenv("OPENAI_API_KEY", "").strip())
    provider = "huggingface_local" if local_ready else "openai" if openai_enabled else "huggingface_local"
    enabled = local_ready or openai_enabled
    model = LOCAL_LLM_MODEL if provider == "huggingface_local" else os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    return {
        "llm_enabled": enabled,
        "model_ready": local_ready,
        "provider": provider,
        "model": model,
        "source_count": len(KNOWLEDGE),
        "mode": "rag_llm" if enabled else "rag_only",
    }


@router.post("/chat")
async def assistant_chat(request: ChatRequest, _user: dict = Depends(require_roles("patient", "doctor"))):
    question = request.question.strip()
    if not question:
        raise HTTPException(422, "Saisissez une question")
    language = _language(question)
    greeting = _normalize(question).strip()
    if greeting in {"bonjour", "bonsoir", "salut", "hello", "hi", "hey", "salam", "salam alaykoum", "marhaba", "مرحبا", "اهلا"}:
        answer = {
            "fr": "Bonjour ! Posez-moi une question générale sur HeartLab.",
            "en": "Hello! Ask me a general question about HeartLab.",
            "ar": "مرحباً! اطرح سؤالاً عاماً عن HeartLab.",
        }[language]
        return {"answer": answer, "mode": "rag_only", "llm_enabled": bool(os.getenv("OPENAI_API_KEY", "").strip()), "notice": None, "sources": []}
    sources = retrieve(question)
    normalized = _normalize(question)
    asks_about_schedule = (
        ("rendez vous" in normalized or "rendezvous" in normalized or "agenda" in normalized or "calendrier" in normalized or "appointment" in normalized or "calendar" in normalized or "مواعيد" in normalized)
        and any(term in normalized for term in ("aujourd", "maintenant", "mes", "mon", "il y a", "est ce", "appointment", "today", "my", "do i", "have", "هل", "اليوم"))
    )
    if asks_about_schedule:
        lang = language
        sources = [next(item for item in KNOWLEDGE if item["id"] == f"appointments-{lang}")]
        answer = (
            "لا أستطيع الاطلاع على مواعيدك الشخصية من هنا. افتح قسم المواعيد في حسابك لمعرفة مواعيد اليوم."
            if lang == "ar" else
            "Je ne peux pas consulter vos rendez-vous personnels ici. Ouvrez l’onglet « Rendez-vous » de votre espace pour voir ceux d’aujourd’hui."
        )
        mode = "rag_only"
        notice = None
    else:
        answer = None
        mode = "rag_only"
        notice = None
    urgent_terms = ("chest pain", "douleur thoracique", "difficulty breathing", "difficulte a respirer", "ألم الصدر", "صعوبة التنفس")
    if not asks_about_schedule and any(_normalize(term) in normalized for term in urgent_terms):
        lang = language
        urgent = next(item for item in KNOWLEDGE if item["id"] == f"urgent-{lang}")
        sources = [urgent]
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    local_model_ready = await _local_model_ready() if request.use_llm and not asks_about_schedule else False
    if not asks_about_schedule and request.use_llm and sources and local_model_ready:
        try:
            answer, mode = await _generate_with_local_model(question, sources), "rag_llm"
        except HTTPException:
            answer = _document_answer(sources, language)
            mode = "rag_fallback"
            notice = "Le modèle local tarde à répondre. Voici les informations RAG locales."
    elif not asks_about_schedule and request.use_llm and api_key and sources:
        try:
            answer, mode = await _generate_with_llm(question, sources), "rag_llm"
        except HTTPException:
            answer = _document_answer(sources, language)
            mode = "rag_fallback"
            notice = "Le service IA tarde à répondre. Voici les informations locales tirées des sources."
    elif not asks_about_schedule:
        answer = _document_answer(sources, language)
        mode = "rag_only" if not request.use_llm or api_key else "rag_fallback" if not local_model_ready else "rag_no_match"
        if request.use_llm and not api_key and not local_model_ready:
            notice = "Le modèle local est encore en cours de chargement. Cette réponse rapide provient du RAG local."
    return {
        "answer": answer, "mode": mode, "llm_enabled": local_model_ready or bool(api_key), "notice": notice,
        "sources": [{"id": item["id"], "title": item["title"], "source": item["source"], "url": item["url"]} for item in sources],
    }
