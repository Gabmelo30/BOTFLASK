# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime
from database import DatabaseManager, get_application_path
import tempfile

app = Flask(__name__)
app.secret_key = 'chave_secreta_app_rest_gyn'

# Instanciar o gerenciador de banco de dados
db = DatabaseManager()
db.insert_klb_tomador()

# Configurações para upload de arquivos
UPLOAD_FOLDER = os.path.join(get_application_path(), 'uploads')
ALLOWED_EXTENSIONS = {'txt'}

# Criar pasta de uploads se não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    notas_fiscais = db.get_all_notas_fiscais()
    return render_template('index.html', notas_fiscais=notas_fiscais)

@app.route('/api/notas')
def get_notas():
    try:
        notas_df = db.get_all_notas_fiscais()
        if notas_df.empty:
            return jsonify([])
            
        # Convert DataFrame to list of dictionaries
        notas_list = notas_df.to_dict('records')
        
        # Format dates and numbers
        for nota in notas_list:
            if 'dt_emissao' in nota and nota['dt_emissao']:
                nota['dt_emissao'] = pd.to_datetime(nota['dt_emissao']).strftime('%Y-%m-%d')
            if 'dt_pagamento' in nota and nota['dt_pagamento']:
                nota['dt_pagamento'] = pd.to_datetime(nota['dt_pagamento']).strftime('%Y-%m-%d')
            if 'valor_nf' in nota:
                nota['valor_nf'] = float(nota['valor_nf']) if nota['valor_nf'] else 0
            if 'aliquota' in nota:
                nota['aliquota'] = float(nota['aliquota']) if nota['aliquota'] else 0
                
        return jsonify(notas_list)
    except Exception as e:
        print(f"Erro ao obter notas fiscais: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/nota', methods=['GET', 'POST'])
def nota_fiscal():
    if request.method == 'POST':
        # Processar o formulário de cadastro de nota fiscal
        try:
            dados = {
                'referencia': request.form.get('referencia', ''),
                'cadastrado_goiania': request.form.get('cadastrado_goiania', 'Não'),
                'fora_pais': request.form.get('fora_pais', 'Não'),
                'cnpj': request.form.get('cnpj', ''),
                'fornecedor': request.form.get('fornecedor', ''),
                'uf': request.form.get('uf', ''),
                'municipio': request.form.get('municipio', ''),
                'cod_municipio': request.form.get('cod_municipio', ''),
                'inscricao_municipal': request.form.get('inscricao_municipal', ''),
                'tipo_servico': request.form.get('tipo_servico', ''),
                'base_calculo': request.form.get('base_calculo', '00 - Base de cálculo '),
                'num_nf': request.form.get('num_nf', ''),
                'dt_emissao': request.form.get('dt_emissao', ''),
                'dt_pagamento': request.form.get('dt_pagamento', ''),
                'aliquota': float(request.form.get('aliquota', 0)),
                'valor_nf': float(request.form.get('valor_nf', 0)),
                'recolhimento': request.form.get('recolhimento', ''),
                'recibo': request.form.get('recibo', '')
            }
            
            # Inserir fornecedor e obter o ID
            fornecedor_id = db.insert_fornecedor(
                dados['cnpj'],
                dados['fornecedor'],
                dados['uf'],
                dados['municipio'],
                dados['cod_municipio'],
                dados['fora_pais'],
                dados['cadastrado_goiania']
            )
            
            if fornecedor_id is None:
                flash('Erro ao salvar fornecedor', 'error')
                return redirect(url_for('nota_fiscal'))
                
            # Preparar dados para inserção da nota fiscal
            nota_fiscal_data = {
                "referencia": dados['referencia'],
                "CNPJ": dados['cnpj'],
                "Fornecedor_ID": fornecedor_id,
                "Inscrição Municipal": dados['inscricao_municipal'],
                "Tipo de Serviço": dados['tipo_servico'],
                "Base de Cálculo": dados['base_calculo'],
                "Nº NF": dados['num_nf'],
                "Dt. Emissão": dados['dt_emissao'],
                "Dt. Pagamento": dados['dt_pagamento'],
                "Aliquota": dados['aliquota'],
                "Valor NF": dados['valor_nf'],
                "Recolhimento": dados['recolhimento'],
                "RECIBO": dados['recibo'],
                "UF": dados['uf'],
                "Município": dados['municipio'],
                "Código Município": dados['cod_municipio'],
                "cadastrado_goiania": dados['cadastrado_goiania'],
                "fora_pais": dados['fora_pais']
            }
            
            # Verificar se é edição ou cadastro novo
            nota_id = request.form.get('nota_id')
            if nota_id:
                # Atualizar nota fiscal existente
                if db.update_nota_fiscal(nota_id, nota_fiscal_data):
                    flash('Nota fiscal atualizada com sucesso!', 'success')
                else:
                    flash('Erro ao atualizar nota fiscal', 'error')
            else:
                # Inserir nova nota fiscal
                if db.insert_nota_fiscal(nota_fiscal_data):
                    flash('Nota fiscal cadastrada com sucesso!', 'success')
                else:
                    flash('Erro ao cadastrar nota fiscal', 'error')
                    
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Erro ao processar formulário: {str(e)}', 'error')
            return redirect(url_for('nota_fiscal'))
    
    # GET - Exibir formulário
    ufs = db.get_all_ufs()
    tipos_servico = db.get_all_tipos_servico()
    bases_calculo = db.get_all_bases_calculo()
    recolhimentos = db.get_all_recolhimentos()
    nota = None
    
    # Se for edição, carregar dados da nota
    nota_id = request.args.get('id')
    if nota_id:
        nota = db.get_nota_fiscal_by_id(nota_id)
    
    return render_template(
        'nota_fiscal.html', 
        ufs=ufs, 
        tipos_servico=tipos_servico,
        bases_calculo=bases_calculo,
        recolhimentos=recolhimentos,
        nota=nota
    )

@app.route('/nota/excluir/<int:nota_id>', methods=['POST'])
def excluir_nota(nota_id):
    if db.delete_nota_fiscal(nota_id):
        flash('Nota fiscal excluída com sucesso!', 'success')
    else:
        flash('Erro ao excluir nota fiscal', 'error')
    return redirect(url_for('index'))

@app.route('/municipios/<uf>', methods=['GET'])
def get_municipios(uf):
    municipios = db.get_municipios_by_uf(uf)
    return jsonify(municipios)

@app.route('/fornecedor/<cnpj>', methods=['GET'])
def get_fornecedor(cnpj):
    fornecedor = db.get_fornecedor_by_cnpj(cnpj)
    if fornecedor:
        return jsonify({
            'descricao_fornecedor': fornecedor[0],
            'uf': fornecedor[1],
            'municipio': fornecedor[2],
            'cod_municipio': fornecedor[3]
        })
    return jsonify({})

@app.route('/cod_municipio', methods=['GET'])
def get_codigo_municipio():
    uf = request.args.get('uf')
    municipio = request.args.get('municipio')
    if uf and municipio:
        codigo = db.get_cod_municipio(uf, municipio)
        return jsonify({'codigo': codigo})
    return jsonify({'codigo': ''})

@app.route('/importar-municipios', methods=['GET', 'POST'])
def importar_municipios():
    if request.method == 'POST':
        # Verificar se o arquivo foi enviado
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo enviado', 'error')
            return redirect(request.url)
        
        arquivo = request.files['arquivo']
        
        # Se o usuário não selecionar um arquivo
        if arquivo.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)
        
        if arquivo and allowed_file(arquivo.filename):
            filename = secure_filename(arquivo.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            arquivo.save(filepath)
            
            try:
                if db.import_municipios_from_txt(filepath):
                    flash('Municípios importados com sucesso!', 'success')
                else:
                    flash('Erro ao importar municípios', 'error')
            except Exception as e:
                flash(f'Erro ao importar municípios: {str(e)}', 'error')
            
            # Remover arquivo após importação
            os.remove(filepath)
            return redirect(url_for('index'))
    
    return render_template('importar_municipios.html')

@app.route('/tomadores', methods=['GET'])
def listar_tomadores():
    tomadores = db.get_all_tomadores()
    return render_template('tomadores.html', tomadores=tomadores)

@app.route('/tomadores/novo', methods=['GET', 'POST'])
def novo_tomador():
    if request.method == 'POST':
        dados = {
            'razao_social': request.form.get('razao_social', ''),
            'cnpj': request.form.get('cnpj', ''),
            'inscricao': request.form.get('inscricao', ''),
            'usuario': request.form.get('usuario', '')
        }
        
        if db.insert_tomador(dados):
            flash('Tomador cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_tomadores'))
        else:
            flash('Erro ao cadastrar tomador', 'error')
    
    return render_template('form_tomador.html')

def insert_tomador(self, dados):
    """
    Insere um novo tomador no banco de dados
    
    :param dados: Dicionário com os dados do tomador
    :return: True se inserido com sucesso, False caso contrário
    """
    conn = self.create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Campos obrigatórios
            razao_social = dados.get('razao_social', '').strip()
            cnpj = dados.get('cnpj', '').strip()
            inscricao = dados.get('inscricao', '').strip()
            usuario = dados.get('usuario', '').strip()
            
            if not razao_social:
                print("Erro: Razão Social é obrigatória")
                return False
            
            # Inserir apenas os campos básicos para garantir compatibilidade
            cursor.execute("""
                INSERT INTO tb_config_tomador 
                (razao_social, cnpj, cae_inscricao, usuario_prefeitura, data_atualizacao)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (razao_social, cnpj, inscricao, usuario))
            
            # Registrar os dados inseridos para debug
            print(f"Tomador inserido: {razao_social}, {cnpj}, {inscricao}, {usuario}")
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Erro detalhado ao inserir tomador: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()
    return False

@app.route('/tomadores/adicionar', methods=['GET', 'POST'])
def adicionar_tomador():
    """Adiciona um novo tomador"""
    if request.method == 'POST':
        # Coletar dados do formulário
        dados = {
            'razao_social': request.form.get('razao_social', ''),
            'cnpj': request.form.get('cnpj', ''),
            'inscricao': request.form.get('inscricao', ''),
            'usuario': request.form.get('usuario', '')
        }
        
        # Adicionar log para debug
        print(f"Dados recebidos do formulário: {dados}")
        
        # Validações básicas
        if not dados['razao_social']:
            flash('Razão Social é obrigatória', 'danger')
            return render_template('form_tomador.html')
        
        if not dados['cnpj']:
            flash('CNPJ é obrigatório', 'danger')
            return render_template('form_tomador.html')
        
        # Limpar CNPJ de formatação
        dados['cnpj'] = ''.join(filter(str.isdigit, dados['cnpj']))
        
        # Tentar inserir no banco de dados
        if db.insert_tomador(dados):
            flash('Tomador cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_tomadores'))
        else:
            flash('Erro ao cadastrar tomador. Verifique os dados e tente novamente.', 'danger')
    
    # Para GET, apenas renderizar o formulário
    return render_template('form_tomador.html')

@app.route('/tomadores/excluir/<int:tomador_id>', methods=['POST'])
def excluir_tomador(tomador_id):
    if db.delete_tomador(tomador_id):
        flash('Tomador excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir tomador', 'error')
    return redirect(url_for('listar_tomadores'))

@app.route('/tomadores/editar/<int:tomador_id>', methods=['GET', 'POST'])
def editar_tomador(tomador_id):
    """Edita um tomador existente"""
    # Obter dados do tomador
    tomadores = db.get_all_tomadores()
    tomador = next((t for t in tomadores if t[0] == tomador_id), None)
    
    if not tomador:
        flash('Tomador não encontrado', 'danger')
        return redirect(url_for('listar_tomadores'))
    
    if request.method == 'POST':
        dados = {
            'id': tomador_id,
            'razao_social': request.form.get('razao_social', '').strip(),
            'cnpj': request.form.get('cnpj', '').strip(),
            'inscricao': request.form.get('inscricao', '').strip(),
            'usuario': request.form.get('usuario', '').strip()
        }
        
        # Validações básicas
        if not dados["razao_social"]:
            flash('Razão Social é obrigatória', 'danger')
            return render_template('form_tomador.html', edit_mode=True, tomador=tomador)
        
        # Remover caracteres não numéricos do CNPJ
        dados["cnpj"] = ''.join(filter(str.isdigit, dados["cnpj"]))
        
        # Atualizar tomador
        if db.update_tomador(dados):
            flash('Tomador atualizado com sucesso!', 'success')
            return redirect(url_for('listar_tomadores'))
        else:
            flash('Erro ao atualizar tomador', 'danger')
    
    # Para GET, renderizar o formulário com dados preenchidos
    return render_template('form_tomador.html', edit_mode=True, tomador=tomador)

@app.route('/exportar-excel', methods=['GET', 'POST'])
def exportar_excel():
    try:
        # Criar arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        temp_file.close()
        
        if db.export_to_excel(temp_file.name):
            # Enviar arquivo para download
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name='notas_fiscais.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            flash('Erro ao exportar dados', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        flash(f'Erro ao exportar para Excel: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/exportar-txt-especifico', methods=['GET', 'POST'])
def exportar_txt_especifico():
    try:
        # Criar arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8')
        
        # Escrever o conteúdo específico
        content = """H242545920250610KLB ACCOUTING CONTABILIDADE EMPRESARIAL EIRELI                                                      
09238316000190 N                                                                                                                                                                                        
20250610marcelo.santos@kblcontabilidade.com.br2.9.7N                                                                                                                                                      
D00000100000000000000012345678000190Empresa ABC Ltda                                  12.345.678/0001-900000000005000000000000000175002025011520250115                                                  J                         050022025011500350300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000017500000000000000000000000000000000000000
T000010000000000"""
        
        temp_file.write(content)
        temp_file.close()
        
        # Enviar arquivo para download
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name='exportacao_especifica.txt',
            mimetype='text/plain'
        )
    except Exception as e:
        flash(f'Erro ao exportar para TXT: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/exportar-txt', methods=['GET', 'POST'])
def exportar_txt():
    try:
        # Criar arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8')
        temp_file.close()
        
        if db.export_to_txt(temp_file.name):
            # Enviar arquivo para download
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name='notas_fiscais.txt',
                mimetype='text/plain'
            )
        else:
            flash('Erro ao exportar dados para TXT', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        flash(f'Erro ao exportar para TXT: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/limpar-notas', methods=['POST'])
def limpar_notas():
    if request.form.get('confirmar') == 'sim':
        if db.limpar_notas_fiscais():
            flash('Notas fiscais removidas com sucesso!', 'success')
        else:
            flash('Erro ao limpar tabela de notas fiscais', 'error')
    return redirect(url_for('index'))

@app.route('/limpar-tomadores', methods=['POST'])
def limpar_tomadores():
    if request.form.get('confirmar') == 'sim':
        if db.limpar_tomadores():
            flash('Tomadores removidos com sucesso!', 'success')
        else:
            flash('Erro ao limpar tabela de tomadores', 'error')
    return redirect(url_for('listar_tomadores'))

@app.route('/api/estatisticas')
def get_estatisticas():
    conn = db.create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Total de notas fiscais
            cursor.execute("SELECT COUNT(*) FROM tb_notas_fiscais")
            total_notas = cursor.fetchone()[0]
            
            # Total de fornecedores
            cursor.execute("SELECT COUNT(*) FROM tb_fornecedores")
            total_fornecedores = cursor.fetchone()[0]
            
            # Total de tomadores
            cursor.execute("SELECT COUNT(*) FROM tb_config_tomador")
            total_tomadores = cursor.fetchone()[0]
            
            # Valor total das notas
            cursor.execute("SELECT COALESCE(SUM(valor_nf), 0) FROM tb_notas_fiscais")
            valor_total = float(cursor.fetchone()[0] or 0)
            
            # Valor total do ISS
            cursor.execute("SELECT COALESCE(SUM(valor_nf * aliquota / 100), 0) FROM tb_notas_fiscais")
            valor_iss = float(cursor.fetchone()[0] or 0)
            
            return jsonify({
                'total_notas': total_notas,
                'total_fornecedores': total_fornecedores,
                'total_tomadores': total_tomadores,
                'valor_total': valor_total,
                'valor_iss': valor_iss
            })
            
        except Exception as e:
            print(f"Erro ao obter estatísticas: {e}")
            return jsonify({
                'total_notas': 0,
                'total_fornecedores': 0,
                'total_tomadores': 0,
                'valor_total': 0,
                'valor_iss': 0
            }), 500
        finally:
            conn.close()
    
    return jsonify({
        'total_notas': 0,
        'total_fornecedores': 0,
        'total_tomadores': 0,
        'valor_total': 0,
        'valor_iss': 0
    }), 500

@app.route('/fornecedores')
def listar_fornecedores():
    """Lista todos os fornecedores cadastrados"""
    fornecedores = db.get_all_fornecedores()
    return render_template('fornecedores.html', fornecedores=fornecedores)

@app.route('/fornecedores/novo', methods=['GET', 'POST'])
def novo_fornecedor():
    """Adiciona um novo fornecedor"""
    if request.method == 'POST':
        dados = {
            'cnpj': request.form.get('cnpj', '').strip(),
            'descricao_fornecedor': request.form.get('descricao_fornecedor', '').strip(),
            'uf': request.form.get('uf', '').strip(),
            'municipio': request.form.get('municipio', '').strip(),
            'cod_municipio': request.form.get('cod_municipio', '').strip(),
            'fora_pais': request.form.get('fora_pais', 'Não'),
            'cadastrado_goiania': request.form.get('cadastrado_goiania', 'Não')
        }
        
        # Validações básicas
        if not dados['cnpj']:
            flash('CNPJ é obrigatório', 'danger')
            return render_template('form_fornecedor.html')
        
        if not dados['descricao_fornecedor']:
            flash('Nome do fornecedor é obrigatório', 'danger')
            return render_template('form_fornecedor.html')
        
        # Limpar CNPJ de formatação
        dados['cnpj'] = ''.join(filter(str.isdigit, dados['cnpj']))
        
        # Inserir fornecedor
        if db.insert_fornecedor(
            dados['cnpj'],
            dados['descricao_fornecedor'],
            dados['uf'],
            dados['municipio'],
            dados['cod_municipio'],
            dados['fora_pais'],
            dados['cadastrado_goiania']
        ):
            flash('Fornecedor cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_fornecedores'))
        else:
            flash('Erro ao cadastrar fornecedor', 'danger')
    
    # Para GET, renderizar o formulário
    ufs = db.get_all_ufs()
    return render_template('form_fornecedor.html', ufs=ufs)

@app.route('/fornecedores/editar/<int:fornecedor_id>', methods=['GET', 'POST'])
def editar_fornecedor(fornecedor_id):
    """Edita um fornecedor existente"""
    fornecedor = db.get_fornecedor_by_id(fornecedor_id)
    
    if not fornecedor:
        flash('Fornecedor não encontrado', 'danger')
        return redirect(url_for('listar_fornecedores'))
    
    if request.method == 'POST':
        dados = {
            'id': fornecedor_id,
            'cnpj': request.form.get('cnpj', '').strip(),
            'descricao_fornecedor': request.form.get('descricao_fornecedor', '').strip(),
            'uf': request.form.get('uf', '').strip(),
            'municipio': request.form.get('municipio', '').strip(),
            'cod_municipio': request.form.get('cod_municipio', '').strip(),
            'fora_pais': request.form.get('fora_pais', 'Não'),
            'cadastrado_goiania': request.form.get('cadastrado_goiania', 'Não')
        }
        
        # Validações básicas
        if not dados['descricao_fornecedor']:
            flash('Nome do fornecedor é obrigatório', 'danger')
            return render_template('form_fornecedor.html', fornecedor=fornecedor, edit_mode=True)
        
        # Limpar CNPJ de formatação
        dados['cnpj'] = ''.join(filter(str.isdigit, dados['cnpj']))
        
        # Atualizar fornecedor
        if db.update_fornecedor(dados):
            flash('Fornecedor atualizado com sucesso!', 'success')
            return redirect(url_for('listar_fornecedores'))
        else:
            flash('Erro ao atualizar fornecedor', 'danger')
    
    # Para GET, renderizar o formulário com dados preenchidos
    ufs = db.get_all_ufs()
    return render_template('form_fornecedor.html', fornecedor=fornecedor, ufs=ufs, edit_mode=True)

@app.route('/fornecedores/excluir/<int:fornecedor_id>', methods=['POST'])
def excluir_fornecedor(fornecedor_id):
    """Exclui um fornecedor"""
    if db.delete_fornecedor(fornecedor_id):
        flash('Fornecedor excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir fornecedor', 'error')
    return redirect(url_for('listar_fornecedores'))

@app.route('/fornecedores/limpar', methods=['POST'])
def limpar_fornecedores():
    """Limpa todos os fornecedores"""
    if request.form.get('confirmar') == 'sim':
        if db.limpar_fornecedores():
            flash('Fornecedores removidos com sucesso!', 'success')
        else:
            flash('Erro ao limpar tabela de fornecedores', 'error')
    return redirect(url_for('listar_fornecedores'))

if __name__ == '__main__':
    app.run(debug=True)