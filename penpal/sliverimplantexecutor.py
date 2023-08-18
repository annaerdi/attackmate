"""
sliverimplantexecutor.py
============================================
Generate Sliver Implants
"""

import asyncio
import os
from sliver import SliverClientConfig, SliverClient
from sliver.protobuf import client_pb2
from .variablestore import VariableStore
from .baseexecutor import BaseExecutor, ExecException, Result
from .schemas import SliverImplantCommand


class SliverImplantExecutor(BaseExecutor):

    def __init__(self, cmdconfig=None, *,
                 varstore: VariableStore,
                 sliver_config=None):
        self.sliver_config = sliver_config
        self.client = None
        self.client_config = None
        self.result = Result("", 1)

        if self.sliver_config.config_file:
            self.client_config = SliverClientConfig.parse_config_file(sliver_config.config_file)
            self.client = SliverClient(self.client_config)
        super().__init__(varstore, cmdconfig)

    async def connect(self) -> None:
        if self.client:
            await self.client.connect()
            version = await self.client.version()
            self.logger.debug(version)

    def log_command(self, command: SliverImplantCommand):
        self.logger.info(f"Generating Sliver-Implant: '{command.name}'")
        loop = asyncio.get_event_loop()
        coro = self.connect()
        loop.run_until_complete(coro)

    def prepare_implant_config(self, command: SliverImplantCommand) -> client_pb2.ImplantConfig:
        c2 = client_pb2.ImplantC2()
        c2.URL = command.c2url
        c2.Priority = 0
        outformat = client_pb2.OutputFormat.EXECUTABLE
        if command.format == "SERVICE":
            outformat = client_pb2.OutputFormat.SERVICE

        if command.format == "SHARED_LIB":
            outformat = client_pb2.OutputFormat.SHARED_LIB

        if command.format == "SHELLCODE":
            outformat = client_pb2.OutputFormat.SHELLCODE

        implconfig = client_pb2.ImplantConfig()
        implconfig.C2.extend([c2])
        implconfig.IsBeacon = False
        target = command.target.split("/")
        implconfig.GOOS = target[0]
        implconfig.GOARCH = target[1]
        implconfig.Name = command.name
        implconfig.Format = outformat
        implconfig.FileName = "linux_implant"
        return implconfig

    def save_implant(self, implant: client_pb2.Generate) -> str:
        if implant.filepath:
            implant_path = implant.filepath
        else:
            implant_path = os.path.join("/tmp/", implant.File.Name)

        if os.path.exists(implant_path):
            os.remove(implant_path)

        with open(implant_path, "wb") as new_file:
            new_file.write(implant.File.Data)

        return implant_path

    async def generate_implant(self, command: SliverImplantCommand):
        implconfig = self.prepare_implant_config(command)

        if self.client is None:
            raise ExecException("SliverClient is not defined")

        builds = await self.client.implant_builds()
        if len(builds) > 0:
            self.logger.debug("Implant found. Delete it")
            await self.client.delete_implant_build(command.name)

        implant = await self.client.generate_implant(implconfig)
        length = len(implant.File.Data)
        self.result.stdout = f"Created Sliver-Implant: {implant.File.Name}. with {length} bytes"
        implant_path = self.save_implant(implant)
        self.logger.debug(f"Saved {implant.File.Name} to {implant_path}")
        self.result.returncode = 0

    def _exec_cmd(self, command: SliverImplantCommand) -> Result:
        loop = asyncio.get_event_loop()
        coro = self.generate_implant(command)
        loop.run_until_complete(coro)
        return self.result
