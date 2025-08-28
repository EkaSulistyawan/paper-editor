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
    return render(request, "paper_editor.html", {"entry": {"paragraph": initial_paragraph}})

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
            formatted_html = "\n".join(formatted_paragraphs)

            return JsonResponse({"formatted": formatted_html})

        except json.JSONDecodeError:
            return JsonResponse({"formatted": "<p>Error parsing input.</p>"})

    return JsonResponse({"formatted": "<p>Invalid request.</p>"})

def home(request):
    return render(request, 'htmls/writer.html')

import os
import json
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt

def media_context(request):
    media_dir = settings.MEDIA_ROOT
    media_images = [f for f in os.listdir(media_dir) if f.lower().endswith(('.png','.jpg','.jpeg','.gif'))]
    media_references = [f for f in os.listdir(media_dir) if f.lower().endswith('.txt')]

    # Handle figure upload
    if request.method == "POST" and request.FILES.get('figure'):
        figure = request.FILES['figure']
        fs = FileSystemStorage(location=settings.MEDIA_ROOT)
        fs.save(figure.name, figure)
        return redirect('media_context')

    return render(request, "htmls/preface.html", {
        "media_images": media_images,
        "media_references": media_references,
        "MEDIA_URL": settings.MEDIA_URL
    })

@csrf_exempt
def remove_image(request):
    if request.method == "POST":
        data = json.loads(request.body)
        filename = data.get('filename')
        file_path = os.path.join(settings.MEDIA_ROOT, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return JsonResponse({'success': True})
    return JsonResponse({'success': False})

def save_state(request):
    if request.method == "POST":
        # Example: Save current references text
        references_text = request.POST.get('references_text', '')
        save_path = os.path.join(settings.MEDIA_ROOT, 'references_saved.txt')
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(references_text)
        return redirect('media_context')
    return redirect('media_context')


















media_images = os.listdir(os.path.join(settings.MEDIA_ROOT)) 

def editor(request):
    media_dir = os.path.join(settings.MEDIA_ROOT)
    media_images = [f for f in os.listdir(media_dir) if f.lower().endswith(('.png','.jpg','.jpeg','.gif'))]
    
    headings_file = os.path.join(settings.BASE_DIR, "headings.json")
    if os.path.exists(headings_file):
        import json
        with open(headings_file) as f:
            headings = json.load(f)
    else:
        headings = []

    index = request.session.get("editor_index", 0)
    if "matrix" not in request.session:
        request.session["matrix"] = []

    matrix = request.session["matrix"]

    # current entry
    if index < len(matrix):
        entry = matrix[index]
    else:
        entry = {"paragraph":"", "references":"", "images":[]}

    if request.method == "POST":
        action = request.POST.get("action")
        paragraph = request.POST.get("paragraph")
        references = request.POST.get("references")
        selected_images = request.POST.getlist("selected_images")
        selected_heading = request.POST.get("heading")

        entry = {
            "paragraph": paragraph,
            "references": references,
            "images": selected_images,
            "heading":selected_heading
        }

        if index < len(matrix):
            matrix[index] = entry
        else:
            matrix.append(entry)

        request.session["matrix"] = matrix
        request.session.modified = True

        # navigation
        if action == "next":
            index += 1
        elif action == "previous" and index > 0:
            index -= 1
        request.session["editor_index"] = index

        # load next entry
        if index < len(matrix):
            entry = matrix[index]
        else:
            entry = {"paragraph":"", "references":"", "images":[]}

    return render(request, "htmls/editor.html", {
        "entry": entry,
        "index": index,
        "total": 100,
        "media_images": media_images,
        "headings": headings,
        "MEDIA_URL": settings.MEDIA_URL
    })


from django.shortcuts import render, redirect
from django.conf import settings
import os

def manage_headings_images(request):
    # Predefined headings stored in a JSON file or DB
    headings_file = os.path.join(settings.BASE_DIR, "headings.json")
    if os.path.exists(headings_file):
        import json
        with open(headings_file) as f:
            headings = json.load(f)
    else:
        headings = []

    # List all images in media folder
    media_dir = os.path.join(settings.MEDIA_ROOT)
    media_images = [f for f in os.listdir(media_dir) if f.lower().endswith(('.png','.jpg','.jpeg','.gif'))]
    print(media_images)
    if request.method == "POST":
        remove_title = request.POST.get("remove_heading")
        if remove_title:
            def remove_heading(hlist, title):
                for h in hlist[:]:  # iterate over copy to allow removal
                    if h["title"] == title:
                        hlist.remove(h)
                        return True
                    if remove_heading(h.get("sub", []), title):
                        return True
                return False
            remove_heading(headings, remove_title)
            # Save back to JSON file or DB


        # Handle new headings
        new_heading = request.POST.get("new_heading")
        parent = request.POST.get("parent_heading")
        if new_heading:
            if parent:
                # find parent recursively
                def add_subheading(hlist, parent_title):
                    for h in hlist:
                        if h["title"] == parent_title:
                            h.setdefault("sub", []).append({"title": new_heading, "sub":[]})
                            return True
                        if add_subheading(h.get("sub", []), parent_title):
                            return True
                    return False
                add_subheading(headings, parent)
            else:
                headings.append({"title": new_heading, "sub":[]})

        # Handle uploaded images
        uploaded_file = request.FILES.get("image")
        if uploaded_file:
            with open(os.path.join(media_dir, uploaded_file.name), "wb+") as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)

        # Save headings back
        import json
        with open(headings_file, "w") as f:
            json.dump(headings, f, indent=2)

        return redirect("manage_headings_images")

    return render(request, "htmls/manage.html", {
        "headings": headings,
        "media_images": media_images,
        "MEDIA_URL": settings.MEDIA_URL
    })




@csrf_exempt  # since we're sending JSON via AJAX
def ai_recommendation(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            paragraph = data.get("paragraph", "")
            reference = data.get("reference","")

            # Long template with multiple lines
            template = """
            You are an expert reviewer. Read the paragraph and references carefully.
            Provide concise, constructive feedback focusing on clarity, logic, and relevance.
            Make sure the reference is approrpiate.

            Paragraph:
            {paragraph}

            References:
            {reference}

            Instructions:
            - Be polite and constructive
            - Highlight strong points
            - Suggest improvements
            - Keep feedback concise but informative
            """
            prompt = PromptTemplate(
                input_variables=["paragraph", "reference"],
                template=template
            )

            # New style: prompt | llm
            runnable = prompt | llm
            comment = runnable.invoke({"paragraph": paragraph, "reference": reference})
            # comment = f"Dummy comment for paragraph: {paragraph[:50]}..."  # first 50 chars

            return JsonResponse({"comment": comment})

        except Exception as e:
            print(str(e))
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"comment": ""})

import os, json
from django.conf import settings
from django.shortcuts import render

def preview(request):
    # Get session data
    matrix = request.session.get("matrix", [])  # list of entries
    paragraphs = [entry.get("paragraph", "") for entry in matrix]

    return render(request, "htmls/preview.html", {"paragraphs": paragraphs})
from django.http import JsonResponse

def compile_json(request):
    matrix = request.session.get("matrix", [])
    paragraphs = [entry.get("paragraph", "") for entry in matrix]
    return JsonResponse({"paragraphs": paragraphs})