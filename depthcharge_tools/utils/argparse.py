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


class _MethodDecorator:
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.__name__ = None
        self.__self__ = None
        self.__func__ = None

        if args and callable(args[0]):
            self.wrap(args[0])
            args = args[1:]

        self._args = args
        self._kwargs = kwargs

    def __copy__(self):
        if self.__func__ is not None:
            args = (self.__func__, *self._args)
            kwargs = self._kwargs
        else:
            args = self._args
            kwargs = self._kwargs

        obj = type(self)(*args, **kwargs)
        obj.__name__ = self.__name__

        return obj

    def __get__(self, instance, owner):
        if self.__self__ is not None:
            return self

        if instance is None:
            self.__self__ = owner
            return self

        if self.__name__ not in instance.__dict__:
            bound = copy.copy(self)
            bound.__self__ = instance
            instance.__dict__[self.__name__] = bound

        return instance.__dict__[self.__name__]

    def __set_name__(self, owner, name):
        self.__name__ = name

    @property
    def __call__(self):
        if self.__self__ is None:
            return self.wrap

        if self.__func__ is None:
            return None

        call = self.__func__.__get__(self, type(self))
        self.__signature__ = inspect.signature(call)

        return call

    def wrap(self, func):
        if not callable(func):
            raise TypeError("Can't wrap non-callable objects")

        self.__func__ = func
        functools.update_wrapper(self, func)
        self.__name__ = func.__name__

        return self


class Argument(_MethodDecorator):
    class _unset:
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = None
        self.action = None
        self._inputs = Argument._unset
        self._value = Argument._unset

    def wrap(self, wrapped):
        if isinstance(wrapped, Argument):
            group = Group()

            group.add(wrapped)
            if group.__name__ is None:
                group.__name__ = wrapped.__name__
            group.__doc__ = wrapped.__doc__
            wrapped.__doc__ = None

            if self.__name__ is None:
                self.__name__ = wrapped.__name__
            self.wrap(wrapped.__wrapped__)
            self.__doc__ = None
            group.add(self)

            return group

        if isinstance(wrapped, Group):
            group = wrapped

            if self.__name__ is None:
                self.__name__ = group.__name__
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

    def build(self, parent):
        args = list(self._args)
        kwargs = dict(self._kwargs)

        action = kwargs.setdefault("action", ArgumentAction)
        dest = kwargs.setdefault("dest", self.__name__)

        if isinstance(action, type) and issubclass(action, argparse.Action):
            kwargs.setdefault("argument", self)
        else:
            kwargs = filter_action_kwargs(action, kwargs)

        return parent.add_argument(*args, **kwargs)

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

        doc = inspect.getdoc(argument)
        help_ = doc.split("\n\n")[0] if doc else None

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


class Group(_MethodDecorator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._arguments = []

    def __copy__(self):
        group = super().__copy__()

        for arg in self._arguments:
            group.add(copy.copy(arg))

        return group

    def wrap(self, func):
        if isinstance(func, Argument):
            self.add(func)
            return self

        return super().wrap(func)

    def build(self, parent):
        args = list(self._args)
        kwargs = dict(self._kwargs)

        doc = inspect.getdoc(self)
        if doc:
            blocks = doc.split("\n\n")
            title = blocks[0].replace("\n", " ")
            desc = "\n\n".join(blocks[1:])
        else:
            title = self.__name__
            desc = None

        title = kwargs.setdefault("title", title)
        desc = kwargs.setdefault("description", desc)

        parser = parent.add_argument_group(*args, **kwargs)

        for arg in self._arguments:
            arg.__self__ = self.__self__
            arg.build(parser)

        return parser

    def add(self, arg):
        self._arguments.append(arg)
        arg.group = self
        return arg


class Subparsers(_MethodDecorator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commands = []

    def __copy__(self):
        subcommands = super().__copy__()

        for cmd in self._commands:
            subcommands.add(copy.copy(cmd))

        return subcommands

    def wrap(self, func):
        if isinstance(func, Command):
            self.add(func)
            return self

        return super().wrap(func)

    def build(self, parent):
        args = list(self._args)
        kwargs = dict(self._kwargs)

        doc = inspect.getdoc(self)
        if doc:
            blocks = doc.split("\n\n")
            title = blocks[0].replace("\n", " ")
            desc = "\n\n".join(blocks[1:])
        else:
            title = self.__name__
            desc = None

        title = kwargs.setdefault("title", title)
        desc = kwargs.setdefault("description", desc)
        dest = kwargs.setdefault("dest", self.__name__)

        subparsers = parent.add_subparsers(*args, **kwargs)

        for cmd in self._commands:
            cmd.build(subparsers)

        return subparsers

    def add(self, cmd):
        self._commands.append(cmd)
        return cmd


class CommandMeta(type):
    def __new__(mcls, name, bases, attrs, **kwargs):
        call = attrs.get("__call__", None)

        if call is not None:
            def __call__(self, **kwargs):
                tmp = copy.copy(self)
                for kwarg, value in kwargs.items():
                    setattr(tmp, kwarg, value)
                return call(tmp)
            attrs["__call__"] = __call__

        cls = super().__new__(mcls, name, bases, attrs)
        cls.__kwargs = kwargs
        return cls

    def items(cls):
        def order(tup):
            attr, value = tup
            return (
                isinstance(value, Group),
                isinstance(value, Argument),
                isinstance(value, Subparsers),
                isinstance(value, Command),
            )
        pairs = (
            (k, v) for k, v in vars(cls).items()
            if not k.startswith("_")
        )
        return sorted(pairs, key=order, reverse=True)

    def groups(cls):
        yield from (
            (k, v) for k, v in cls.items()
            if isinstance(v, Group)
        )

    def arguments(cls):
        yield from (
            (k, v) for k, v in cls.items()
            if isinstance(v, Argument)
        )

    def subparsers(cls):
        yield from (
            (k, v) for k, v in cls.items()
            if isinstance(v, Subparsers)
        )

    def subcommands(cls):
        yield from (
            (k, v) for k, v in cls.items()
            if isinstance(v, Command)
        )

    def subcommand(cls, arg):
        if isinstance(arg, type) and issubclass(arg, Command):
            setattr(cls, arg.__name__, arg)
            return arg

        def add_subcommand(cmd):
            setattr(cls, arg, cmd)
            cmd.__name__ = arg
            return cmd

        return add_subcommand

    @property
    def parser(cls):
        return cls.build()

    def build(cls, parent=None):
        kwargs = dict(cls.__kwargs)

        doc = inspect.getdoc(cls)
        if doc:
            blocks = doc.split("\n\n")

            for i, block in enumerate(blocks):
                if block.strip("- ") == "":
                    desc = "\n\n".join(blocks[:i])
                    epilog = "\n\n".join(blocks[i+1:])
                    break
            else:
                desc = doc
                epilog = None

        else:
            desc = None
            epilog = None

        desc = kwargs.setdefault("description", desc)
        epilog = kwargs.setdefault("epilog", epilog)
        formatter = kwargs.setdefault(
            "formatter_class",
            argparse.RawDescriptionHelpFormatter,
        )

        if parent is None:
            parser = argparse.ArgumentParser(**kwargs)

        else:
            desc = kwargs.pop("description")
            help_ = kwargs.setdefault("help", desc)
            parser = parent.add_parser(cls.__name__, **kwargs)

        subparsers = None

        for attr, value in cls.items():
            if isinstance(value, Group):
                group = getattr(cls, attr)
                group.build(parser)

            elif isinstance(value, Argument):
                arg = getattr(cls, attr)
                if arg.group is None:
                    arg.build(parser)

            elif isinstance(value, Subparsers):
                obj = getattr(cls, attr)
                subparsers = obj.build(parser)

            elif isinstance(value, type) and issubclass(value, Command):
                cmd = getattr(cls, attr)
                cmd.__self__ = cls

                if subparsers is None:
                    subparsers = parser.add_subparsers()
                cmd.build(subparsers)

        parser.set_defaults(__command=cls)

        return parser


class Command(metaclass=CommandMeta):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._args = args
        self._kwargs = kwargs

    def __copy__(self):
        cmd = type(self)(*self._args, **self._kwargs)
        cmd.__name__ = self.__name__

        return cmd



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
