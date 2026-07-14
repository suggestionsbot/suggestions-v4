import lightbulb

AUTO_DEFER = lightbulb.ExecutionStep("AUTO_DEFER")


@lightbulb.hook(AUTO_DEFER)
async def early_ephemeral_defer(
    _: lightbulb.ExecutionPipeline, ctx: lightbulb.Context
) -> None:
    await ctx.defer(ephemeral=True)
