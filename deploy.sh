#!/bin/bash
echo "🔄 Adicionando alterações..."
git add .

echo "✍️ Informe a mensagem do commit:"
read mensagem

git commit -m "$mensagem"
echo "🚀 Enviando para o GitHub..."
git push origin main && echo "✅ Deploy concluído!" || echo "❌ Falha ao enviar"
