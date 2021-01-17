#! /usr/bin/env python3

import argparse
import functools
import inspect
import logging
import sys


class Argument:
    def __init__(self, *args, **kwargs):
        self._func = None
        self._name = None
        self._args = args
        self._kwargs = kwargs
        self._command = None
        self._inputs = None
        self._value = None

        if args and callable(args[0]):
            self._args = args[1:]
            self.wrap(args[0])

    @property
    def __call__(self):
        func = self.func
        if func is not None:
            return func
        else:
            return self.wrap

    def wrap(self, func):
        if isinstance(func, Argument):
            raise NotImplementedError

        if self._func is None:
            if callable(func):
                self._func = func
                self.name = func.__name__

        elif func != self._func:
            raise ValueError(func)

        return self

    def __get__(self, instance, owner):
        if not isinstance(instance, Command):
            return self

        name = self.name
        if name in instance.__dict__:
            arg = instance.__dict__[name]
            if arg.inputs is not None:
                return arg.value
            else:
                return arg

        copy = self.copy()
        copy.command = instance
        instance.__dict__[name] = copy

        return copy

    def __set__(self, instance, value):
        name = self.name
        if isinstance(instance, Command) and name in instance.__dict__:
            arg = instance.__dict__[name]
        else:
            arg = self

        arg._inputs = value

    def __set_name__(self, owner, name):
        if not issubclass(owner, Command):
            return
        self.name = name

    def copy(self):
        if self._func is not None:
            return type(self)(self._func, *self._args, **self._kwargs)
        else:
            return type(self)(*self._args, **self._kwargs)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if self._name is None:
            self._name = name
        elif self._name != name:
            raise ValueError(name)

    @property
    def command(self):
        return self._command

    @command.setter
    def command(self, command):
        if self._command is not None:
            raise ValueError(command)

        self._command = command

        name = self.name
        args = list(self._args)
        kwargs = dict(self._kwargs)

        action = self.action
        help = self.help
        dest = self.dest
        metavar = self.metavar
        nargs = self.nargs
        const = self.const

        if args and args[0] in (dest, metavar):
            args = args[1:]

        if action is not None:
            kwargs.setdefault("action", action)
        if help is not None:
            kwargs.setdefault("help", help)
        if dest is not None:
            kwargs.setdefault("dest", dest)
        if metavar is not None:
            kwargs.setdefault("metavar", metavar)
        if nargs is not None:
            kwargs.setdefault("nargs", nargs)
        if const is not None:
            kwargs.setdefault("const", const)

        command.parser.add_argument(*args, **kwargs)

    @property
    def func(self):
        if self._func is None or self._command is None:
            return None

        return functools.partial(
            self._func,
            self._command,
        )

    def is_optional(self):
        if not self._args:
            return False

        if self._command is None:
            prefix_chars = "-"
        else:
            prefix_chars = self._command.parser.prefix_chars

        return self._args[0][0] in prefix_chars

    def is_positional(self):
        return not self.is_optional()

    @property
    def action(self):
        nargs = self.nargs
        if nargs is None:
            return None

        if nargs == 0:
            return "store_const"
        else:
            return "store"

    @property
    def const(self):
        nargs = self.nargs
        if nargs is None:
            return None

        if nargs == 0:
            return []
        else:
            return None

    @property
    def dest(self):
        if self.name is not None:
            return self.name
        elif self.is_positional() and self._args:
            return self._args[0]

    @property
    def metavar(self):
        if self.name is not None:
            if self.is_positional() and self._args:
                return self._args[0]

    @property
    def nargs(self):
        func = self.func
        if func is None:
            return None

        params = inspect.signature(func).parameters

        if any(
            param.kind == inspect.Parameter.VAR_POSITIONAL
            or param.kind == inspect.Parameter.VAR_KEYWORD
            for name, param in params.items()
        ):
            return "*"

        return len(params)

    @property
    def help(self):
        return inspect.getdoc(self._func)

    @property
    def inputs(self):
        return self._inputs

    @property
    def value(self):
        if self._value is not None:
            return self._value

        value = self.func(*self.inputs)
        self._value = value
        return value


class Command:
    def __init__(self, *args, **kwargs):
        self.parser = argparse.ArgumentParser(*args, **kwargs)

        for attr, value in vars(self.__class__).items():
            if isinstance(value, Argument):
                arg = getattr(self, attr)


class OldCommand:
    def __init__(self, name=None, parent=None):
        self._name = name
        self._parent = parent

        if hasattr(parent, "_prog"):
            self._prog = "{} {}".format(self._parent._prog, self._name)
        else:
            self._prog = self._name

        self._parser = self._init_parser()
        self._arguments = None
        self._options = None
        self._commands = None

        if hasattr(self, "_init_arguments"):
            self._arguments = self._parser.add_argument_group(
                title="Positional arguments",
            )
            self._init_arguments(self._arguments)

        option_inits = []
        cmd = self
        if hasattr(self, "_init_options"):
            option_inits += [self._init_options]
        while cmd is not None:
            if hasattr(cmd, "_init_globals"):
                option_inits += [cmd._init_globals]
            cmd = cmd._parent

        if option_inits:
            self._options = self._parser.add_argument_group(
                title="Options",
            )
            for init in option_inits:
                init(self._options)

        if hasattr(self, "_init_commands"):
            self._commands = self._parser.add_subparsers(
                title="Supported commands",
                prog=self._prog,
            )
            self._init_commands()

        self._parser.set_defaults(_command=self)

    def __call__(self, *args, **kwargs):
        pass

    def _init_parser(self, *args, **kwargs):
        if self._parent is None:
            return argparse.ArgumentParser(
                *args,
                prog=self._prog,
                **kwargs,
            )

        else:
            return self._parent._commands.add_parser(
                self._name,
                *args,
                help=kwargs.get("description"),
                **kwargs,
            )

    def _main(self, *argv):
        if len(argv) == 0:
            prog, *argv = sys.argv

        args = self._parser.parse_args(argv)
        command = args._command
        kwargs = vars(args)
        del kwargs["_command"]

        try:
            output = command(**kwargs)
            if output is not None:
                print(output)
        except ValueError as err:
            command._parser.error(err.args[0])
        except OSError as err:
            logging.getLogger(self.__module__).error(err)
            sys.exit(err.errno)


class LoggingLevelAction(argparse.Action):
    def __init__(self, option_strings, dest, level, nargs=None, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)
        self.level = level

    def __call__(self, parser, namespace, values, option_string=None):
        logger = logging.getLogger()

        if isinstance(self.level, str):
            level = logger.getEffectiveLevel()
            if self.level.startswith("-"):
                logger.setLevel(level - int(self.level[1:]))
            elif self.level.startswith("+"):
                logger.setLevel(level + int(self.level[1:]))

        else:
            self.logger.setLevel(self.level)


class MixedArgumentsAction(argparse.Action):
    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        cls._selectors = {}
        cls._nargs = {}

    def __init__(self, option_strings, dest, select=None, **kwargs):
        super().__init__(option_strings, dest, **kwargs)
        self._selectors[select] = self.dest
        self._nargs[dest] = self.nargs

    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            return
        elif values is getattr(namespace, self.dest):
            return
        elif not isinstance(values, list):
            values = [values]

        for value in values:
            chosen_dest = None
            for select, dest in self._selectors.items():
                if callable(select) and select(value):
                    chosen_dest = dest

            if chosen_dest is not None:
                try:
                    self._set_value(namespace, chosen_dest, value)
                    continue
                except argparse.ArgumentError as err:
                    parser.error(err.message)

            for dest, nargs in self._nargs.items():
                try:
                    self._set_value(namespace, dest, value)
                    break
                except argparse.ArgumentError as err:
                    continue
            else:
                parser.error(err.message)

    def _set_value(self, namespace, dest, value):
        nargs = self._nargs[dest]
        current = getattr(namespace, dest)

        if nargs is None or nargs == "?":
            if current is not None:
                fmt = "Cannot have multiple {} args '{}' and '{}'."
                msg = fmt.format(dest, current, value)
                raise argparse.ArgumentError(self, msg)
            else:
                setattr(namespace, dest, value)

        elif isinstance(nargs, int) and len(current) > nargs:
            fmt = "Cannot have more than {} {} args {}."
            msg = fmt.format(nargs, dest, current + value)
            raise argparse.ArgumentError(self, msg)

        elif current is None:
            setattr(namespace, dest, [value])

        else:
            current.append(value)
