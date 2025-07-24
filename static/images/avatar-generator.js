/**
 * Gerador de Avatar Fallback para SIGE
 * Cria avatares automaticamente quando a foto não carrega
 */

function gerarCorPorNome(nome) {
    // Gerar cor baseada no hash do nome
    let hash = 0;
    for (let i = 0; i < nome.length; i++) {
        hash = nome.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    // Converter para cor hexadecimal
    const cores = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6'
    ];
    
    return cores[Math.abs(hash) % cores.length];
}

function obterIniciais(nome) {
    const palavras = nome.trim().split(' ');
    if (palavras.length >= 2) {
        return palavras[0][0] + palavras[palavras.length - 1][0];
    }
    return palavras[0].substring(0, 2);
}

function criarAvatarSVG(nome, tamanho = 120) {
    const iniciais = obterIniciais(nome).toUpperCase();
    const cor = gerarCorPorNome(nome);
    
    return `data:image/svg+xml;base64,${btoa(`
        <svg width="${tamanho}" height="${tamanho}" xmlns="http://www.w3.org/2000/svg">
            <circle cx="${tamanho/2}" cy="${tamanho/2}" r="${tamanho/2}" fill="${cor}"/>
            <text x="${tamanho/2}" y="${tamanho/2 + 8}" font-family="Arial" font-size="${tamanho/3}" 
                  font-weight="bold" text-anchor="middle" fill="white">${iniciais}</text>
        </svg>
    `)}`;
}

// Função global para corrigir imagens quebradas
function corrigirImagemQuebrada(img) {
    if (img.dataset.nome) {
        img.src = criarAvatarSVG(img.dataset.nome, img.width || 120);
        img.onerror = null; // Evitar loop infinito
    } else {
        img.src = '/static/images/default-avatar.svg';
    }
}

// Aplicar automaticamente a todas as imagens de funcionário
document.addEventListener('DOMContentLoaded', function() {
    const imagens = document.querySelectorAll('img[alt*="Foto de"], img[alt="Avatar padrão"]');
    
    imagens.forEach(img => {
        // Extrair nome do alt text
        const altText = img.alt;
        if (altText.includes('Foto de ')) {
            const nome = altText.replace('Foto de ', '');
            img.dataset.nome = nome;
        }
        
        // Configurar fallback para erro
        img.onerror = function() {
            corrigirImagemQuebrada(this);
        };
    });
});