# Step 08 Guidance: Art Style Confirmation

Step 08 gates the art pipeline on an explicit style choice. When manual gates are enabled and no `style_confirmation.json` exists, it returns `waiting_confirmation` so the GUI can open the style confirmation dialog. When gates are skipped or a confirmation already exists, it writes the approved confirmation artifact and lets the pipeline continue.
