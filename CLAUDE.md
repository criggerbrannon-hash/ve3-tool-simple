# VE3 Tool Pro - AI Video Generation System

## Overview

VE3 Tool Pro là hệ thống tự động chuyển đổi voice/audio thành video hoàn chỉnh với AI-generated imagery.

## Project Structure

```
ve3-tool-simple/
├── run_srt.py              # Voice to SRT (Whisper)
├── run_excel_api.py        # SRT to Excel (AI đạo diễn)
├── run_worker.py           # Image/Video generation
├── run_worker_video.py     # Video-only processing
├── run_edit.py             # Manual editing GUI
├── vm_manager.py           # VM orchestration
├── modules/                # Core modules
│   ├── voice_to_srt.py     # Whisper transcription
│   ├── progressive_prompts.py  # Step-by-step prompt generation (QUAN TRỌNG)
│   ├── excel_manager.py    # Excel workbook management
│   ├── google_flow_api.py  # Google Flow API client
│   ├── drission_flow_api.py # Browser automation
│   └── ...
├── config/
│   ├── settings.yaml       # Main configuration
│   └── accounts.json       # Chrome profiles
└── PROJECTS/               # Output directory
    └── {code}/
        ├── {code}.srt
        ├── {code}_prompts.xlsx
        ├── img/
        └── video/
```

## Main Workflow

```
Audio → SRT → Excel (AI đạo diễn) → Images → Videos → Final
```

### Step-by-step Excel Generation (progressive_prompts.py)

1. **Step 1**: Phân tích story → story_analysis sheet
2. **Step 1.5**: Chia story segments → story_segments sheet
3. **Step 2**: Tạo characters → characters sheet
4. **Step 3**: Tạo locations → locations sheet
5. **Step 4**: Director plan → director_plan sheet
6. **Step 4.5**: Scene planning → scene_planning sheet
7. **Step 5**: Scene prompts → scenes sheet

## Key Files When Debugging

- **modules/progressive_prompts.py**: Logic tạo Excel prompts
- **modules/excel_manager.py**: Đọc/ghi Excel
- **modules/google_flow_api.py**: API calls to Google Flow
- **config/settings.yaml**: API keys và settings

## Common Issues

1. **Thiếu scene trong Excel**: Kiểm tra Step 4 và Step 5 trong progressive_prompts.py
2. **API fail**: Kiểm tra API keys trong settings.yaml
3. **Excel format error**: Kiểm tra excel_manager.py

## Running

```bash
# Tạo Excel từ SRT
python run_excel_api.py PROJECT_CODE

# Chạy worker tạo ảnh/video
python run_worker.py
```

## Testing

```bash
# Check Python syntax
python -m py_compile modules/progressive_prompts.py

# Test import
python -c "from modules.progressive_prompts import ProgressivePromptsGenerator; print('OK')"
```

## Dependencies

- Python 3.8+
- openpyxl (Excel)
- requests (API)
- openai-whisper (SRT)
- DrissionPage (Browser automation)
