#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import logging
from . import config
from .sensors import update_leds
from .display import draw_face
from . import state
try:
    from . import voice_assistant
except Exception:
    try:
        import voice_assistant
    except Exception:
        voice_assistant = None
try:
    from . import smart_ac
except Exception:
    try:
        import smart_ac
    except Exception:
        smart_ac = None

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['PEOPLE_COUNT'] = 0

@app.route("/", methods=["GET", "POST"])
def index():
    # global people_count
    if request.method == "POST":
        if "increase" in request.form:
            state.incr_people(1)
            # Recompute AC suggestion immediately so UI reflects change without waiting for the thread
            try:
                if smart_ac:
                    s = smart_ac.suggest_temp()
                    ed = state.get_energy_data()
                    if ed.get('ac_override'):
                        # preserve manual override: only update suggestion
                        state.update_energy_data({"ac_suggestion": int(s)})
                    else:
                        state.update_energy_data({"ac_suggestion": int(s), "ac_current": int(s), "ac_override": False})
            except Exception:
                logger.exception('Failed to update AC suggestion after people increase')
        if "decrease" in request.form:
            state.incr_people(-1)
            # Recompute AC suggestion immediately so UI reflects change without waiting for the thread
            try:
                if smart_ac:
                    s = smart_ac.suggest_temp()
                    ed = state.get_energy_data()
                    if ed.get('ac_override'):
                        state.update_energy_data({"ac_suggestion": int(s)})
                    else:
                        state.update_energy_data({"ac_suggestion": int(s), "ac_current": int(s), "ac_override": False})
            except Exception:
                logger.exception('Failed to update AC suggestion after people decrease')
        update_leds()
        draw_face(mouth_open=True)
    # Safely read values from shared energy_data and normalize missing keys
    ed = state.get_energy_data()
    temp = ed.get("temperature")
    hum = ed.get("humidity")
    current_usage = ed.get("current_usage", 0.0)
    total_consumption = ed.get("total_consumption", 0.0)
    ac_sugg = ed.get("ac_suggestion")
    ac_curr = ed.get("ac_current")
    ac_override = ed.get("ac_override", False)
    # Provide a unified cost value (prefer `cost`, fall back to `cost_usd`)
    cost_value = ed.get("cost", ed.get("cost_usd", 0.0))
    try:
        return render_template(
            'dashboard_template.html',
            people_count=state.get_people_count(),
            current_usage=current_usage,
            total_consumption=total_consumption,
            cost=cost_value,
            temp=temp,
            hum=hum,
            ac_suggestion=ac_sugg,
            ac_current=ac_curr,
            ac_override=ac_override
        )
    except Exception as e:
        logger.exception("Failed to render dashboard: %s", e)
        # Return a minimal error page so Flask debug doesn't leak internals in production
        return f"Template render error: {e}", 500

@app.route("/data")
def data():
    # Normalize keys so front-end always sees consistent names
    st = state.get_state()
    normalized = dict(st.get('energy_data', {}))
    normalized.setdefault('cost', normalized.get('cost', normalized.get('cost_usd', 0.0)))
    normalized['people_count'] = st.get('people_count', 0)
    # Ensure numeric types for the front end
    try:
        normalized['current_usage'] = float(normalized.get('current_usage', 0.0))
        normalized['total_consumption'] = float(normalized.get('total_consumption', 0.0))
        # AC fields: allow None when not present so UI can show '--'
        if 'ac_suggestion' in normalized and normalized['ac_suggestion'] is not None:
            try:
                normalized['ac_suggestion'] = int(normalized['ac_suggestion'])
            except Exception:
                normalized['ac_suggestion'] = None
        else:
            normalized['ac_suggestion'] = None

        if 'ac_current' in normalized and normalized['ac_current'] is not None:
            try:
                normalized['ac_current'] = int(normalized['ac_current'])
            except Exception:
                normalized['ac_current'] = None
        else:
            normalized['ac_current'] = None

        normalized['ac_override'] = bool(normalized.get('ac_override', False))
    except Exception:
        logger.exception('Non-numeric energy values in energy_data')
    return jsonify(normalized)

def run_server():
    logger.info("Starting web server on 0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)


@app.route('/voice', methods=['POST'])
def voice_endpoint():
    """Accept JSON {"text": "..."} from the dashboard and execute via voice_assistant.interpret_and_execute
    Falls back to an error if voice_assistant is unavailable.
    """
    data = request.get_json(silent=True) or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'no text provided'}), 400
    if not voice_assistant or not hasattr(voice_assistant, 'interpret_and_execute'):
        return jsonify({'error': 'voice assistant not available'}), 500
    try:
        result = voice_assistant.interpret_and_execute(text)
        return jsonify({'result': result})
    except Exception:
        logger.exception('Voice command processing failed')
        return jsonify({'error': 'internal error'}), 500


@app.route('/ac/override', methods=['POST'])
def ac_override_endpoint():
    """Apply a manual AC setpoint. JSON: {"value": 24}
    Uses smart_ac.apply_manual_setpoint when available.
    """
    data = request.get_json(silent=True) or {}
    val = data.get('value')
    if val is None:
        return jsonify({'error': 'no value provided'}), 400
    if not smart_ac or not hasattr(smart_ac, 'apply_manual_setpoint'):
        return jsonify({'error': 'smart_ac not available'}), 500
    try:
        smart_ac.apply_manual_setpoint(float(val))
        # return updated state snapshot for convenience
        ed = state.get_energy_data()
        return jsonify({'result': 'override applied', 'ac_current': ed.get('ac_current'), 'ac_override': True})
    except Exception as e:
        logger.exception('Failed to apply AC override')
        return jsonify({'error': str(e)}), 500


@app.route('/ac/override/clear', methods=['POST'])
def ac_override_clear_endpoint():
    """Clear manual AC override (calls smart_ac.clear_manual_setpoint)."""
    if not smart_ac or not hasattr(smart_ac, 'clear_manual_setpoint'):
        return jsonify({'error': 'smart_ac not available'}), 500
    try:
        smart_ac.clear_manual_setpoint()
        ed = state.get_energy_data()
        return jsonify({'result': 'override cleared', 'ac_override': False, 'ac_current': ed.get('ac_current')})
    except Exception as e:
        logger.exception('Failed to clear AC override')
        return jsonify({'error': str(e)}), 500
