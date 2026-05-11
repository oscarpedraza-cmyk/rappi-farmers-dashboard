# Rappi Farmers Dashboard — Guía de uso

## Instalación (primera vez)

```bash
cd C:\Users\oscar.pedraza\rappi-farmers-dashboard
pip install -r requirements.txt
```

## Ejecutar el dashboard

```bash
streamlit run app.py
```

Se abre automáticamente en http://localhost:8501

---

## Flujo semanal

1. **Sube el Sheet Maestro** (sidebar izquierdo) — el mismo `Sheet_Maestro_Farmers.xlsx`
2. **Configura el día de corte** = día de envío del reporte − 1
3. Revisa el resumen rápido en la pantalla principal
4. Navega por las páginas del menú izquierdo
5. **Guarda el snapshot histórico** antes de cerrar (botón en el sidebar)

---

## Páginas

| Página | Para qué |
|---|---|
| 🏠 Principal | Resumen rápido y semáforo del equipo |
| 📊 Vista Equipo | Análisis gerencial macro — heatmap, rankings, diagnóstico |
| 👤 Vista Farmer | Análisis supervisor individual — métricas, productividad cruzada, recomendaciones |
| 📈 Histórico | Tendencias semanales — evolución por farmer y por palanca |
| 💰 Compensación | Calculadora de variable en tiempo real + simulador |

---

## Fórmulas clave

- **Progreso del mes** = (día_corte − 1) / días_mes × 100
- **Net Revenue Adj** = ATT_Rev_real% − Progreso%
- **Qualifier productividad** = ≥ 90% (solo Zoho Voice + Treble + Meets)
- **Variable score** = ADS(35%) + MD(20%) + MDPro(20%) + Churn(25%)
- **Revenue Share ADS** = 10% (90–100%) / 20% (100–120%) / 30% (>120%)
