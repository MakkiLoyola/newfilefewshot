from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
import torch
from peft import LoraConfig
from trl import SFTTrainer
from rouge import Rouge


def finetune_llama_med():
     assessments = [
        "Assessment: A 60 year old woman with recurrent ALL with CNS involvement s/p Omaya removal due to VRE contamination & SDH evacuation.  She is now doing well and awake s/p extubation, afebrile and her WBC count is trending downward.",
        "Assessment: 53 yoM w/ a h/o schizoaffective disorder presents s/p fall with atrial flutter with a rapid ventricular response, intracranial lesion, and lung mass who  has new dx of squamous cell lung cancer with extension into left atrium, and was started on IV amio load overnight.",
        "Assessment: 45 year old man with pmh significant for type I DM, ESRD on hemodialysis, labile blood pressure, presenting with hypertensive emergency.",
        "Assessment: 75yo M w/stage IV lung cancer, DM type 2, afib, HTN, CRI p/w pleuritic CP, PNA, hypotention and afib with RVR.",
        "Assessment: ADVERSE DRUG EVENT (ADR, ADE, MEDICATION TOXICITY) tylenol od, admit level 115.5 ASSESSMENT & PLAN: 30 y.o. F with toxic ingestion and acetaminophen toxicity, presently sedated and intubated for airway protection.",
        "Assessment: 75 YOF with SAH, SDH, R gluteal hematoma, R occipital superficial laceration ",
    ]

    summaries = [
        "Summary: CNS VRE; LEUKOCYTOSIS; ALL",
        "Summary: Atrial & Ventricular Ectopy; L hilar mass/Brain Mass; Hypoxic respiratory failure; Weakness over right UE/LE; Schizoaffective disorder",
        "Summary: Hypertensive emergency; Chest Pain; ESRD on HD; DM",
        "Summary: Hypotension; PNA; Pleuritic CP; Afib; Non-small cell lung ca; DM 2; hx CRI ",
        "Summary: Toxic Ingestion; Acetaminophen Toxicity:; # Respiratory Distress; Suicide Attempt ",
        "Summary: seizure; COPD; large gluteal hematoma",
    ]

    data_dict = {
        "assessments": assessments,
        "summaries": summaries
    }

    data = Dataset.from_dict(data_dict)

    # Initialize tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b-hf")
    tokenizer.pad_token = tokenizer.eos_token
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype="float16", bnb_4bit_use_double_quant=True
    )

    model = AutoModelForCausalLM.from_pretrained(
        "meta-llama/Llama-2-7b-hf", quantization_config=bnb_config, device_map={"": 0}
    )
    model.config.use_cache = False
    model.config.pretraining_tp = 1

    # Initialize LoraConfig and TrainingArguments
    peft_config = LoraConfig(
        r=64, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM"
    )

    training_arguments = TrainingArguments(
        output_dir="./llama2_finetuned_medical",
        per_device_train_batch_size=12,
        gradient_accumulation_steps=4,
        optim="paged_adamw_8bit",
        learning_rate=2e-4,
        lr_scheduler_type="linear",
        save_strategy="epoch",
        logging_steps=10,
        num_train_epochs=1,
        max_steps=20,
        fp16=True,
        push_to_hub=True
    )

    # Initialize trainer and train
    trainer = SFTTrainer(
        model=model,
        train_dataset=data,
        peft_config=peft_config,
        dataset_text_field="assessments",  # Column name in your dataset for training
        training_arguments=training_arguments,
        tokenizer=tokenizer,
        packing=False
    )
    
    trainer.train()
    trainer.save_model("./llama2_finetuned_medical")
    trainer.push_to_hub()

def generate_and_evaluate_summaries():
    # Reload the tokenizer and model for evaluation
    tokenizer = AutoTokenizer.from_pretrained("./llama2_finetuned_medical")
    model = AutoModelForCausalLM.from_pretrained("./llama2_finetuned_medical")
    
    rouge = Rouge()
    
    test_assessments = [  # Add your test assessments here
        "34 yo M with a history of Etoh abuse and withdrawal who presented with cough, vomiting, and seized in the ED, concerning for ETOH withdrawal.",
        "GASTROINTESTINAL BLEED, LOWER (HEMATOCHEZIA, BRBPR, GI BLEED, GIB) 74yo male with history of radiation proctitis with recent LGIB, GERD, PVD, and severe aortic stenosis who presents with drop in Hct and BRBPR.",
    ]
    
    reference_summaries = [  # Add your reference summaries here
        "Altered mental status; nfluenza like illness:; Thrombocytopenia:",
        "GI Bleed; Anemia",
    ]
    
    for i, assessment in enumerate(test_assessments):
        generated_summary = generate_summary(model, tokenizer, assessment)
        reference_summary = reference_summaries[i]
        
        print(f"Generated Summary: {generated_summary}")
        print(f"Reference Summary: {reference_summary}")
        
        scores = rouge.get_scores(generated_summary, reference_summary)
        rouge_l_score = scores[0]['rouge-l']
        
        print(f"ROUGE-L Score: {rouge_l_score}")

def generate_summary(model, tokenizer, assessment_text):
    inputs = tokenizer([assessment_text], return_tensors="pt", padding=True, truncation=True)
    summary_ids = model.generate(inputs.input_ids, max_length=50, num_return_sequences=1)
    summary = tokenizer.batch_decode(summary_ids, skip_special_tokens=True)[0]
    return summary

if __name__ == "__main__":
    finetune_llama_med()
    generate_and_evaluate_summaries()
