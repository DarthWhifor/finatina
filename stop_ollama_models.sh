#!/bin/bash
# Skripta za zaustavljanje Ollama modela

echo "📋 Aktivni modeli:"
ollama ps

echo
read -p "👉 Unesi ime modela koji želiš zaustaviti (ili 'all' za sve): " MODEL

if [ "$MODEL" = "all" ]; then
    echo "⏹ Zaustavljam SVE modele..."
    ollama stop all
else
    echo "⏹ Zaustavljam model: $MODEL"
    ollama stop "$MODEL"
fi

echo
echo "✅ Trenutno stanje:"
ollama ps
