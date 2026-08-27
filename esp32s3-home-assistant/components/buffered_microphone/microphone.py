import esphome.codegen as cg
from esphome.components import audio, microphone
import esphome.config_validation as cv
from esphome.const import CONF_ID

CODEOWNERS = []
DEPENDENCIES = ["microphone"]

CONF_SOURCE_MICROPHONE = "source_microphone"
CONF_HISTORY_DURATION = "history_duration"
CONF_PRE_ROLL_DURATION = "pre_roll_duration"

buffered_microphone_ns = cg.esphome_ns.namespace("buffered_microphone")
BufferedMicrophone = buffered_microphone_ns.class_(
    "BufferedMicrophone", microphone.Microphone, cg.Component
)


def _validate_durations(config):
    if config[CONF_PRE_ROLL_DURATION] > config[CONF_HISTORY_DURATION]:
        raise cv.Invalid("pre_roll_duration cannot exceed history_duration")
    return config


def _set_stream_limits(config):
    audio.set_stream_limits(
        min_bits_per_sample=32,
        max_bits_per_sample=32,
        min_channels=1,
        max_channels=1,
        min_sample_rate=16000,
        max_sample_rate=16000,
    )(config)
    return config


CONFIG_SCHEMA = cv.All(
    microphone.MICROPHONE_SCHEMA.extend(
        {
            cv.GenerateID(): cv.declare_id(BufferedMicrophone),
            cv.Required(CONF_SOURCE_MICROPHONE): cv.use_id(microphone.Microphone),
            cv.Optional(CONF_HISTORY_DURATION, default="1s"):
                cv.positive_time_period_milliseconds,
            cv.Optional(CONF_PRE_ROLL_DURATION, default="260ms"):
                cv.positive_time_period_milliseconds,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _validate_durations,
    _set_stream_limits,
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await microphone.register_microphone(var, config)

    source = await cg.get_variable(config[CONF_SOURCE_MICROPHONE])
    cg.add(var.set_source(source))
    cg.add(var.set_history_duration_ms(config[CONF_HISTORY_DURATION].total_milliseconds))
    cg.add(var.set_pre_roll_duration_ms(config[CONF_PRE_ROLL_DURATION].total_milliseconds))
