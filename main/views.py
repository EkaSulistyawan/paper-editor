from django.shortcuts import render
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from django.http import JsonResponse

# Create your views here.
def home(request):
    return render(request, 'main/home.html')


# I need to put results as cookies
# so that it wil be accessed from other functions

# this part of the code loads the arxiv article listd in the input
# 
def doi_list_search(request):
    doi_list = []
    results = []

    if request.method == 'POST':
        # how can you differentiate between button?
        
        text_input = request.POST.get('doi_textarea')
        doi_list = [line.strip() for line in text_input.splitlines() if line.strip()]

        for identifier in doi_list:
            abstract = ''
            source = ''
            if identifier.lower().startswith('10.'):  # likely a DOI
                source = 'DOI'
                url = f"https://api.crossref.org/works/{identifier}"
                r = requests.get(url)
                if r.status_code == 200:
                    data = r.json()
                    abstract_raw = data['message'].get('abstract', 'No abstract available')
                    abstract = BeautifulSoup(abstract_raw, 'html.parser').get_text()
                else:
                    abstract = 'DOI not found'
            else:  # assume arXiv ID
                source = 'arXiv'
                url = f"http://export.arxiv.org/api/query?id_list={identifier}"
                r = requests.get(url)
                if r.status_code == 200:
                    root = ET.fromstring(r.text)
                    ns = {'arxiv': 'http://www.w3.org/2005/Atom'}
                    entry = root.find('arxiv:entry', ns)
                    if entry is not None:
                        abstract = entry.find('arxiv:summary', ns).text.strip()
                    else:
                        abstract = 'arXiv ID not found'
                else:
                    abstract = 'arXiv ID not found'

            results.append({'id': identifier, 'source': source, 'abstract': abstract})
        
        # save text 
        
    if 'proceed-btn' in request.POST:
        request.session['abstract.list'] = results
        return redirect('paper_summary')
    else:
        return render(request, 'main/doi_list.html', {'results': results, 'doi_text': request.POST.get('doi_textarea','')})



"""
############################################################################################################################################################################
For all backend paper editor!
"""

import re
import json
import os
from django.shortcuts import render
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import boto3


# change the LLM to bedrock?
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = "ap-northeast-1"   # Bedrock is only available in specific regions

# Create a client for Bedrock Runtime (for model inference)
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=aws_region,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key
)

def execute_llm(body):
    """
    Executes a call to Amazon Nova Lite on Bedrock
    body must already include 'messages' and 'inferenceConfig'
    """
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": body
                }
            ]
        }
    ]

    body = {
        "messages": messages,
        "inferenceConfig": {
            "maxTokens": 300,
            "temperature": 0.7
        }
    }

    print("Request body:", json.dumps(body, indent=2))

    response = bedrock_client.invoke_model(
        modelId="amazon.nova-lite-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body)
    )
    print("Response received:", response)

    # Parse response
    print(body,json.dumps(body,indent=2))
    result = json.loads(response["body"].read())

    # Nova responses are inside "output" → "message" → "content"
    try:
        summary = result["output"]["message"]["content"][0]["text"]
    except Exception as e:
        print("Error parsing response:", e)
        print("Full response:", result)
        summary = ""

    return summary


# views.py

def paper_editor(request):
    """
    Render the editor page.
    """
    # You can provide some initial paragraph if needed
    abstracts = request.session.get('abstract.list',[])
    print(abstracts)
    initial_paragraph = "Type your text here..."
    return render(request, "htmls/writer.html", {"entry": {"paragraph": initial_paragraph}})

def paper_summary(request):
    """
    Make summary of the paper using Amazon Nova Lite
    """

    
    abstracts = request.session.get('abstract.list', [])

    # Format abstracts into readable text
    formatted_abstracts = []
    for i, paper in enumerate(abstracts, start=1):
        formatted_abstracts.append(
            f"{i}. ({paper.get('source')}:{paper.get('id')}) {paper.get('abstract')}"
        )
    abstracts_text = "\n\n".join(formatted_abstracts)

    # Construct messages in Bedrock's expected format
    prompt_text = (
                        "You are an AI assistant that summarizes scientific papers clearly and concisely.\n\n"
                        f"Please summarize the following paper abstracts in a concise way:\n\n{abstracts_text}\n\n"
                        "Made it one paragraph long."
                    )

    summary = execute_llm(prompt_text)
    
    if 'proceed-btn' in request.POST:
        request.session['abstract.summary'] = summary
        return render(request, "main/paper_editor.html")
    else:
        return render(request, "main/paper_summary.html", {"summary": summary})

def refine_paragraph_with_ai(last_paragraph, request):
    """
    Refine text enclosed in a pattern (default: //...//) using an AI editor.
    Uses saved references if available, and requests refinement via LLM.
    """

    # Load references if they exist
    ref_path = os.path.join(settings.MEDIA_ROOT, "references_saved.txt")
    references = []
    if os.path.exists(ref_path):
        with open(ref_path, 'r', encoding='utf-8') as f:
            references = [line.strip() for line in f if line.strip()]

    def ai_refine(paragraph, request, pattern="//"):
        """
        Creates a robust AI prompt to refine the target pattern in the paragraph.
        """

        # Build reference text for prompt
        ref_text = "\n".join(f"{idx+1}. {r}" for idx, r in enumerate(references))
        if not ref_text:
            ref_text = "No references provided."

        # Extract the portion inside the pattern
        match = re.search(re.escape(pattern) + r"(.*?)" + re.escape(pattern), paragraph, re.DOTALL)
        if not match:
            return paragraph  # No pattern found, return original

        target_text = match.group(1).strip()

        # Build a clear and precise prompt
        prompt = (
            f"You are an expert AI editor. Refine only the text inside {pattern} in the following paragraph, "
            "and return the entire paragraph enclosed by <p></p> with your refinement applied.\n"
            f"'{paragraph}'\n\n"
            f"Text to refine: '{target_text}'\n\n"
            "Refinement should:\n"
            "- Improve grammar, punctuation, and clarity\n"
            "- Maintain the original meaning\n"
            "- Enhance tone for professional and academic readability\n"
            "- Use relevant references if available\n\n"
            f"References:\n{request.session.get('abstract.summary', ref_text)}\n\n"
            "If no reference is relevant, say 'UNABLE TO ADD REFERENCE'. "
            "Return only the refined paragraph without extra commentary."
        )


        print("[DEBUG] Paragraph:", paragraph)
        print("[DEBUG] Prompt:", prompt)

        refined_text = execute_llm(prompt)  # call your LLM here

        print("[DEBUG] Refined Text:", refined_text)
        return refined_text

    # Refine paragraph
    refined_paragraph = ai_refine(last_paragraph, request)

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
    print('Im here')
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            paragraph = data.get("paragraph", "")
            print(paragraph)

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
                    print('Im here!')
                    formatted_paragraphs[j] = refine_paragraph_with_ai(par,request)

            formatted_html = "\n".join(formatted_paragraphs)

            # add final reference
            # formatted_html += add_reference(formatted_html)

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


"""
maybe not used
"""
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


# def refine_paragraph_with_ai(last_paragraph,request):
#         # Load references if the file exists
#     ref_path = os.path.join(settings.MEDIA_ROOT, "references_saved.txt")
#     references = []
#     if os.path.exists(ref_path):
#         with open(ref_path, 'r', encoding='utf-8') as f:
#             references = [line.strip() for line in f if line.strip()]

#     def ai_refine(paragraph,request,pattern="//"):
#         # Smart prompting
#         ref_text = "\n".join(f"- {r}" for r in references) if references else "No references provided."

#         # prompt = (
#         #     f"You are an AI editor. ONLY refine the sentence/text enclosed in {pattern}: '{paragraph}'. "
#         #     "Do not modify anything outside of this text. Keep punctuation, grammar, and clarity. "
#         #     "Return the edited text only, without quotes or extra commentary."S
#         #     f"Additionally, you are given the list of references: {references}"
#         # )


#         # example
#         # Medical imaging is a critical tool in modern healthcare, enabling non-invasive visualization of the internal structures of the body. 
#         # //It plays a vital role in diagnosing diseases, guiding treatment plans, and monitoring patient progress.// Advanced techniques such as MRI, CT scans, and ultrasound provide detailed images that help clinicians make informed decisions. 
#         # The integration of artificial intelligence in medical imaging is also enhancing diagnostic accuracy and efficiency.
#         prompt = (f"""
#         You are an AI editor. ONLY refine the sentence/text enclosed in {pattern}: '{paragraph}'.
#         Do not modify anything outside this text.
#         Keep punctuation, grammar, clarity, and tone intact.
#         Use the following references if relevant:
#         {request.session.get('abstract.summary','')}
#         ONLY refer to the reference given. If impossible, say UNABLE TO ADD REFERENCE.
#         Return only the edited text without quotes or extra commentary.
#         """)
        
#         print('this is inside function')
#         print(paragraph)
#         print(prompt)

#         refined = execute_llm(prompt)  # call your LLM here
#         print(refined)
#         return refined  # replace the original //...//

#     # Use regex to find all occurrences of // ... //
#     refined_paragraph = ai_refine(last_paragraph,request)

#     return refined_paragraph