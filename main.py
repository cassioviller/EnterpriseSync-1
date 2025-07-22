from app import app

# Registrar rotas e blueprints
try:
    from views import main_bp
    app.register_blueprint(main_bp)
    
    from mobile_api import mobile_api
    app.register_blueprint(mobile_api)
    
    print("✅ Blueprints registrados com sucesso")
except Exception as e:
    print(f"⚠️ Erro ao registrar blueprints: {e}")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
