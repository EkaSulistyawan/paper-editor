from django.shortcuts import render, redirect
from django.http import HttpResponse
import fitz  # PyMuPDF
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import re
import json
from django.shortcuts import render
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Local Ollama LLM
llm = OllamaLLM(model="llama3")  # you can change to mistral, gemma, etc.


# views.py
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

def paper_editor(request):
    """
    Render the editor page.
    """
    # You can provide some initial paragraph if needed
    initial_paragraph = "Type your text here..."
    return render(request, "htmls/writer.html", {"entry": {"paragraph": initial_paragraph}})


def refine_paragraph_with_ai(last_paragraph, llm):
    """
    Detects any text enclosed by // ... // in the paragraph,
    sends it to Ollama LLM for refinement, and replaces it.
    """
        # Load references if the file exists
    ref_path = os.path.join(settings.MEDIA_ROOT, "references_saved.txt")
    references = []
    if os.path.exists(ref_path):
        with open(ref_path, 'r', encoding='utf-8') as f:
            references = [line.strip() for line in f if line.strip()]

    def ai_refine(paragraph,pattern="//"):
        # Smart prompting
        ref_text = "\n".join(f"- {r}" for r in references) if references else "No references provided."

        # prompt = (
        #     f"You are an AI editor. ONLY refine the sentence/text enclosed in {pattern}: '{paragraph}'. "
        #     "Do not modify anything outside of this text. Keep punctuation, grammar, and clarity. "
        #     "Return the edited text only, without quotes or extra commentary."S
        #     f"Additionally, you are given the list of references: {references}"
        # )

        print(ref_text)

        prompt = (
            f"You are an AI editor. ONLY refine the sentence/text enclosed in {pattern}: '{paragraph}'.\n"
            "Do not modify anything outside this text.\n"
            "Keep punctuation, grammar, clarity, and tone intact.\n"
            "Use the following references if relevant:\n"
            f"{ref_text}\n"
            "ONLY refer to the reference given. If impossible, say UNABLE TO ADD REFERENCE."
            "Return only the edited text without quotes or extra commentary."
        )

        refined = llm(prompt)  # call your LLM here
        return refined  # replace the original //...//

    # Use regex to find all occurrences of // ... //
    refined_paragraph = ai_refine(last_paragraph)

    return refined_paragraph

def add_figure(paragraph_text: str) -> str:
    """
    Replace lines like 'addfig <filename>' with <img> tags if the file exists.
    Returns HTML-formatted text.
    """
    lines = paragraph_text.splitlines()
    rendered_lines = []

    for line in lines:
        stripped = line.strip()[3:-4] # remove the <p>
        if stripped.lower().startswith("addfig"):
            filename = stripped[7:].strip()
            file_path = os.path.join(settings.MEDIA_ROOT, filename)
            if os.path.exists(file_path):
                img_tag = f'<img src="{settings.MEDIA_URL}{filename}" style="max-width:50%; margin:5px 0;" alt="{filename}">'
                rendered_lines.append(img_tag)
            else:
                rendered_lines.append(f'<span style="color:red;">[Missing image: {filename}]</span>')
        else:
            rendered_lines.append(line or "<br>")

    return "<br>".join(rendered_lines)

@csrf_exempt
def preview_paragraph(request):
    """
    Handle AJAX POST request to preview paragraph.
    Expects JSON: {"paragraph": "..."}
    Returns: {"formatted": "<p>...</p>"}
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            paragraph = data.get("paragraph", "")

            # Example formatting: convert double newlines into <p>
            formatted_paragraphs = [
                f"<p>{p.strip()}</p>"
                for p in paragraph.split("\n\n")
                if p.strip()
            ]

            # add figure
            for j,par in enumerate(formatted_paragraphs):
                formatted_paragraphs[j] = add_figure(par)

            # last_paragraph = (formatted_paragraphs[-1])
            pattern = r"//(.*?)//"
            for j,par in enumerate(formatted_paragraphs):
                if re.findall(pattern, par): # for any sentence enclosed by // <text> // refine with AI
                    formatted_paragraphs[j] = refine_paragraph_with_ai(par, llm)

            formatted_html = "\n".join(formatted_paragraphs)

            # add final reference
            formatted_html += add_reference(formatted_html)

            return JsonResponse({"formatted": formatted_html})

        except json.JSONDecodeError:
            return JsonResponse({"formatted": "<p>Error parsing input.</p>"})

    return JsonResponse({"formatted": "<p>Invalid request.</p>"})


def add_reference(formatted_html):
    """
    Append references from references_saved.txt at the end of the HTML.
    """
    ref_path = os.path.join(settings.MEDIA_ROOT, "references_saved.txt")
    if not os.path.exists(ref_path):
        return ""  # No references

    with open(ref_path, 'r', encoding='utf-8') as f:
        references = [line.strip() for line in f if line.strip()]

    if not references:
        return ""

    # Format references as a simple HTML list
    ref_html = "<h4>References:</h4><ul>"
    for r in references:
        ref_html += f"<li>{r}</li>"
    ref_html += "</ul>"

    return ref_html

def home(request):
    return render(request, 'htmls/writer.html')

import os
import json
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt


REFERENCE_FILE = 'references_saved.txt'

def media_context(request):
    """
    Display figures and references.
    """
    media_dir = settings.MEDIA_ROOT

    # List media images
    media_images = [
        f for f in os.listdir(media_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
    ]

    # List reference files
    media_references = [
        f for f in os.listdir(media_dir)
        if f.lower().endswith('.txt')
    ]

    # Load saved references
    references_text = ''
    saved_references_path = os.path.join(media_dir, REFERENCE_FILE)
    if os.path.exists(saved_references_path):
        with open(saved_references_path, 'r', encoding='utf-8') as f:
            references_text = f.read()

    # Handle figure upload
    if request.method == "POST" and request.FILES.get('figure'):
        figure = request.FILES['figure']
        fs = FileSystemStorage(location=media_dir)
        fs.save(figure.name, figure)
        return redirect('media_context')

    return render(request, "htmls/preface.html", {
        "media_images": media_images,
        "media_references": media_references,
        "references_text": references_text,
        "MEDIA_URL": settings.MEDIA_URL
    })


@csrf_exempt
def remove_image(request):
    """
    Remove an image from media directory via AJAX.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            filename = data.get('filename')
            file_path = os.path.join(settings.MEDIA_ROOT, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                return JsonResponse({'success': True})
        except Exception:
            pass
    return JsonResponse({'success': False})


def save_reference(request):
    """
    Save the current references text to MEDIA_ROOT/references_saved.txt
    Remove all trailing empty lines.
    """
    if request.method == "POST":
        references_text = request.POST.get('references_text', '')

        # Split lines, remove trailing empty lines
        lines = references_text.splitlines()
        # Remove empty lines from the end
        while lines and lines[-1].strip() == '':
            lines.pop()
        # Re-join lines with single newline
        cleaned_text = '\n'.join(lines)

        save_path = os.path.join(settings.MEDIA_ROOT, REFERENCE_FILE)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_text)

        return redirect('media_context')
    return redirect('media_context')

def upload_reference(request):
    """
    Upload a new references file to replace the existing one.
    """
    if request.method == "POST" and request.FILES.get('reference'):
        reference_file = request.FILES['reference']
        fs = FileSystemStorage(location=settings.MEDIA_ROOT)
        fs.save(REFERENCE_FILE, reference_file)  # overwrite
    return redirect('media_context')