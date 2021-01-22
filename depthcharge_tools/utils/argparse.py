#! /usr/bin/env python3

import argparse
import copy
import functools
import inspect
import logging
import sys


def filter_action_kwargs(action, kwargs):
    """
    Filter out the kwargs which argparse actions don't recognize.

    ArgumentParser.add_argument() raises an error on unknown kwargs,
    filter them out. Also unset any values that are Argument._unset.
    """

    allowed = {
        "action", "dest", "nargs", "const", "default", "type",
        "choices", "required", "help", "metavar",
    }
    if action == "store":
        pass

    elif action == "store_const":
        allowed -= {"nargs", "type", "choices"}

    elif action == "store_true":
        allowed -= {"nargs", "const", "type", "choices", "metavar"}

    elif action == "store_false":
        allowed -= {"nargs", "const", "type", "choices", "metavar"}

    elif action == "append":
        pass

    elif action == "append_const":
        allowed -= {"nargs", "type", "choices"}

    elif action == "count":
        allowed -= {"nargs", "const", "type", "choices", "metavar"}

    elif action == "help":
        allowed = {"action", "dest", "default", "help"}

    elif action == "version":
        allowed = {"action", "version", "dest", "default", "help"}

    return {
        key: value
        for key, value in kwargs.items()
        if key in allowed and not value is Argument._unset
    }


class _Named:
    def __init__(self, *args, name=None, **kwargs):
        super().__init__()
        self.__name__ = name

    @property
    def name(self):
        return self.__name__

    @name.setter
    def name(self, name):
        if self.__name__ is None:
            self.__name__ = name
        elif self.__name__ != name:
            raise AttributeError("Can't change name once set")

    def __set_name__(self, owner, name):
        self.name = name


class _AttributeBound(_Named):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__owner = None

    def __get__(self, instance, owner):
        if self.__owner is not None:
            return self

        if instance is None:
            return self

        if self.name not in instance.__dict__:
            bound = copy.copy(self)
            bound.owner = instance
            instance.__dict__[self.name] = bound

        return instance.__dict__[self.name]

    def bind(self, owner):
        if self.__owner is None:
            self.__owner = owner
        elif self.__owner != owner:
            raise ValueError("Can't bind to multiple owners")

    @property
    def owner(self):
        return self.__owner

    @owner.setter
    def owner(self, owner):
        self.bind(owner)


class _Wrapper:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__wrapped__ = None

    def wrap(self, wrapped):
        if self.__wrapped__ is None:
            self.__wrapped__ = wrapped
        elif wrapped != self.__wrapped__:
            raise ValueError("Can't wrap multiple things")

        return self


class _MethodWrapper(_Wrapper, _AttributeBound):
    def __init__(self, *args, **kwargs):
        self.__call = None

        if args and callable(args[0]):
            wrapped = args[0]
            args = args[1:]
        else:
            wrapped = None

        super().__init__(*args, **kwargs)

        if wrapped is not None:
            self.wrap(wrapped)

    def wrap(self, wrapped):
        if not callable(wrapped):
            raise TypeError("Can't wrap non-callable objects")

        super().wrap(wrapped)
        functools.update_wrapper(self, wrapped)
        self.name = wrapped.__name__

        return self

    @property
    def __call__(self):
        if self.owner is None:
            return self.wrap

        if self.__wrapped__ is None:
            return None

        if self.__call is not None:
            return self.__call

        wrap = functools.wraps(self.__wrapped__)
        self.__call = wrap(functools.partial(
            self.__wrapped__,
            self.owner,
        ))
        self.__signature__ = inspect.signature(
            self.__call,
            follow_wrapped=False,
        )

        return self.__call

    @__call__.setter
    def __call__(self, call):
        self.__call = call


class Argument(_MethodWrapper):
    class _unset:
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._args = args
        self._kwargs = kwargs

        if args and args[0] == self.__wrapped__:
            self._args = args[1:]

        self.action = None
        self._inputs = Argument._unset
        self._value = Argument._unset

    def __copy__(self):
        if self.__wrapped__ is not None:
            args = (self.__wrapped__, *self._args)
            kwargs = self._kwargs
        else:
            args = self._args
            kwargs = self._kwargs

        return type(self)(*args, **kwargs)

    def wrap(self, wrapped):
        if isinstance(wrapped, Argument):
            group = Group()

            group.add(wrapped)
            if group.name is None:
                group.name = wrapped.name
            group.__doc__ = wrapped.__doc__
            wrapped.__doc__ = None

            if self.name is None:
                self.name = wrapped.name
            self.wrap(wrapped.__wrapped__)
            self.__doc__ = None
            group.add(self)

            return group

        if isinstance(wrapped, Group):
            group = wrapped

            if self.name is None:
                self.name = group.name
            self.wrap(group._arguments[-1].__wrapped__)
            self.__doc__ = None
            group.add(self)

            return group

        return super().wrap(wrapped)

    def __get__(self, instance, owner):
        arg = super().__get__(instance, owner)

        if arg._inputs is not Argument._unset:
            return arg.value
        elif arg._value is not Argument._unset:
            return arg.value
        else:
            return arg

    def __set__(self, instance, value):
        arg = super().__get__(instance, type(instance))

        if arg._value is Argument._unset:
            arg._inputs = value
        else:
            arg._inputs = Argument._unset
            arg._value = value

    def bind(self, owner):
        if not isinstance(owner, (Command, Group)):
            return

        super().bind(owner)

        name = self.name
        args = list(self._args)
        kwargs = dict(self._kwargs)

        action = kwargs.setdefault("action", ArgumentAction)
        dest = kwargs.setdefault("dest", self.name)

        if isinstance(action, type) and issubclass(action, argparse.Action):
            kwargs.setdefault("argument", self)
        else:
            kwargs = filter_action_kwargs(action, kwargs)

        self.action = owner.parser.add_argument(*args, **kwargs)

        if self.__wrapped__:
            cmd = owner
            while not isinstance(cmd, Command):
                cmd = cmd.owner

            wrap = functools.wraps(self.__wrapped__)
            self.__call__ = wrap(functools.partial(
                self.__wrapped__,
                cmd,
            ))

    @property
    def inputs(self):
        if self._inputs is Argument._unset:
            raise AttributeError("inputs")

        return self._inputs

    @property
    def value(self):
        if self._value is not Argument._unset:
            return self._value

        func = self.__call__
        if func is None:
            value = self.inputs
        else:
            value = self(*self.inputs)

        self._value = value
        return value


class ArgumentAction(argparse.Action):
    def __init__(self, option_strings, dest, argument=None, **kwargs):
        if not isinstance(argument, Argument):
            raise TypeError(
                "ArgumentAction argument 'argument' must be "
                "an Argument object, not '{}'"
                .format(type(argument))
            )
        self.argument = argument

        # callable(arg) returns True even when arg.__call__ is None
        func = self.argument.__call__

        if func is not None:
            params = inspect.signature(
                self.argument,
                follow_wrapped=False,
            ).parameters
        else:
            params = {}

        nargs_min = 0
        nargs_max = 0
        f_args = None
        f_kwargs = None

        for name, param in params.items():
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                f_args = param

            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                f_kwargs = param
                raise NotImplementedError

            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                raise NotImplementedError

            elif param.default == inspect.Parameter.empty:
                nargs_min += 1
                nargs_max += 1

            else:
                nargs_max += 1

        const = None
        default = None
        type_ = None
        choices = None
        required = False
        help_ = inspect.getdoc(argument)
        metavar = tuple(str.upper(s) for s in params.keys())

        # attr = Argument()
        if func is None and not option_strings:
            nargs = 1
            metavar = None

        # attr = Argument("--arg")
        elif func is None:
            nargs = "?"
            metavar = None

        # func(a, *b)
        elif (f_args or f_kwargs) and nargs_min > 0:
            nargs = "+"
            metavar = (f_args or f_kwargs).name.upper()

        # func(*a)
        elif (f_args or f_kwargs) and nargs_min == 0:
            nargs = "*"
            metavar = (f_args or f_kwargs).name.upper()

        # func()
        elif (nargs_min, nargs_max) == (0, 0):
            nargs = 0
            metavar = None

        # func(a=None)
        elif (nargs_min, nargs_max) == (0, 1):
            nargs = "?"
            metavar = metavar[0]

        # func(a, b=None)
        elif nargs_min != nargs_max:
            nargs = "+"
            metavar = metavar[0]

        # func(a, b)
        else:
            nargs = nargs_min
            if not option_strings:
                metavar = None

        super().__init__(
            option_strings,
            dest,
            nargs=kwargs.get("nargs", nargs),
            const=kwargs.get("const", const),
            default=kwargs.get("default", default),
            type=kwargs.get("type", type_),
            choices=kwargs.get("choices", choices),
            required=kwargs.get("required", required),
            help=kwargs.get("help", help_),
            metavar=kwargs.get("metavar", metavar),
        )

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


class Group(_MethodWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._args = args
        self._kwargs = kwargs

        if args and callable(args[0]):
            self._args = args[1:]
            self.wrap(args[0])

        self._arguments = []

    def __copy__(self):
        if self.__wrapped__ is not None:
            args = (self.__wrapped__, *self._args)
            kwargs = self._kwargs
        else:
            args = self._args
            kwargs = self._kwargs

        group = type(self)(*args, **kwargs)

        for arg in self._arguments:
            group.add(copy.copy(arg))

        return group

    def wrap(self, func):
        if isinstance(func, Argument):
            self.add(func)
            return self

        return super().wrap(func)

    def bind(self, owner):
        if not isinstance(owner, Command):
            return

        super().bind(owner)

        args = list(self._args)
        kwargs = dict(self._kwargs)

        doc = inspect.getdoc(self)
        if doc:
            blocks = doc.split("\n\n")
            title = blocks[0].replace("\n", " ")
            desc = "\n\n".join(blocks[1:])
        else:
            title = self.name
            desc = None

        title = kwargs.setdefault("title", title)
        desc = kwargs.setdefault("description", desc)

        self.parser = owner.parser.add_argument_group(*args, **kwargs)

        for arg in self._arguments:
            arg.bind(self)
            owner.__dict__.setdefault(arg.name, arg)

    def add(self, arg):
        self._arguments.append(arg)
        return arg


class Command(_AttributeBound):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._args = args
        self._kwargs = kwargs

        self.parser = argparse.ArgumentParser(*args, **kwargs)

        groups = {}
        arguments = {}
        subcommands = {}

        for attr, value in vars(self.__class__).items():
            if isinstance(value, Group):
                groups[attr] = value

            elif isinstance(value, Argument):
                arguments[attr] = value

            elif isinstance(value, Command):
                subcommands[attr] = value

        for group_name in groups:
            group = getattr(self, group_name)
            groups[group_name] = group

        for arg_name in arguments:
            arg = getattr(self, arg_name)
            arguments[arg_name] = arg

        if subcommands:
            self.subparsers = self.parser.add_subparsers()
        else:
            self.subparsers = None

        for cmd_name in subcommands:
            cmd = getattr(self, cmd_name)
            subcommands[cmd_name] = cmd

        self._arguments = arguments
        self._groups = groups
        self._subcommands = subcommands

    def __copy__(self):
        cmd = type(self)(*self._args, **self._kwargs)
        cmd.name = self.name

        return cmd

    def bind(self, owner):
        if not isinstance(owner, Command):
            return

        super().bind(owner)

        self.parser = owner.subparsers.add_parser(
            self.name,
            *self._args,
            **self._kwargs,
        )

        for group_name in self._groups:
            group = getattr(self, group_name)
            group.bind(self)

        for arg_name in self._arguments:
            arg = getattr(self, arg_name)
            arg.bind(self)

        if self._subcommands:
            self.subparsers = self.parser.add_subparsers()

        for cmd_name in self._subcommands:
            cmd = getattr(self, cmd_name)
            cmd.bind(self)


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
