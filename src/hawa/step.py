"""Ordered portable LBM step extensions; one owner of the stepping entry point."""


class StepCoordinator:
    def __init__(self, simulation):
        self.simulation = simulation
        self.after_collision = []
        self.after_stream = []
        self.names = set()

    def register(self, name, after_collision=None, after_stream=None):
        if name in self.names:
            raise ValueError('Duplicate step extension: ' + name)
        self.names.add(name)
        if after_collision is not None:
            self.after_collision.append(after_collision)
        if after_stream is not None:
            self.after_stream.append(after_stream)

    def __call__(self, *args):
        diagnostic = getattr(self.simulation, 'general_boundary', None)
        def mass():
            return self.simulation.flow.rho()[0][~self.simulation.flow.solid].sum()
        if diagnostic is not None: before = mass()
        self.simulation._collide()
        if diagnostic is not None: collided = mass()
        for callback in self.after_collision:
            callback()
        self.simulation._stream()
        if diagnostic is not None: streamed = mass()
        for callback in self.after_stream:
            callback()
        if diagnostic is not None:
            after = mass()
            diagnostic.report.update(fluid_mass_lu=float(after.cpu()),
                storage_change_lu=float((after-before).cpu()),
                collision_change_lu=float((collided-before).cpu()),
                streaming_exchange_lu=float((streamed-collided).cpu()),
                reconstruction_change_lu=float((after-streamed).cpu()),
                mass_accounting_scope='per-step fluid-population accounting; streaming includes solid reservoirs and external wrap subsequently reconstructed; not a physical flux conservation test')


def coordinator(simulation):
    if not hasattr(simulation, 'boundary_step'):
        simulation.boundary_step = StepCoordinator(simulation)
        simulation._collide_and_stream = simulation.boundary_step
    return simulation.boundary_step

