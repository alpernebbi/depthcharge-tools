#! /usr/bin/env python3

import argparse
import copy
import contextlib
import functools
import inspect
import logging
import sys


def filter_action_kwargs(kwargs, action="store"):
    """
    Filter out the kwargs which argparse actions don't recognize.

    ArgumentParser.add_argument() raises an error on unknown kwargs,
    filter them out. Also unset any values that are None.
    """

    action = kwargs.get("action", action)
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

    elif action is FunctionBindAction:
        allowed |= {"func", "append", "count", "args", "kwargs"}

    else:
        allowed = kwargs.keys()

    action_kwargs = {}
    other_kwargs = {}

    for key, value in kwargs.items():
        if key in allowed:
            action_kwargs[key] = value
        else:
            other_kwargs[key] = value

    return action_kwargs, other_kwargs


class FunctionBindAction(argparse.Action):
    def __init__(
        self,
        option_strings,
        dest,
        func,
        append=False,
        count=False,
        **kwargs,
    ):
        self.signature = inspect.signature(func)
        self.f_args = kwargs.pop("args", ())
        self.f_kwargs = kwargs.pop("kwargs", {})
        self.append = append
        self.count = count

        if append and kwargs.get("nargs", "*") == 0:
            raise ValueError(
                "'{}' action '{}' with append=True must be able to "
                "consume command-line arguments (nargs must not be 0)"
                .format(type(self).__name__, dest)
            )

        if count and kwargs.get("nargs", 0) != 0:
            raise ValueError(
                "'{}' action '{}' with count=True can't consume any "
                "command-line arguments (nargs must be 0)"
                .format(type(self).__name__, dest)
            )

        if count and append:
            raise ValueError(
                "'{}' action '{}' arguments append=True and count=True "
                "are incompatible."
                .format(type(self).__name__, dest)
            )

        if (count or append) and (self.f_args or self.f_kwargs):
            raise NotImplementedError(
                "'{}' action '{}' with append=True or count=True "
                "does not support prebinding arguments yet."
            )

        super_kwargs, _ = filter_action_kwargs(kwargs)
        super().__init__(option_strings, dest, **super_kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if self.dest in (None, argparse.SUPPRESS):
            return

        current = getattr(namespace, self.dest, None)

        if self.nargs in ("?", None):
            values = [values]

        if self.append:
            args = current.args if current else ()
            bound = self.signature.bind_partial(*args, *values)

        elif self.count:
            n = int(current.args[0]) if current else 0
            bound = self.signature.bind(n + 1)

        else:
            bound = self.signature.bind(
                *self.f_args,
                *values,
                **self.f_kwargs,
            )

        setattr(namespace, self.dest, bound)


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

    def __get__(self, instance, owner):
        if self.__self__ is not None:
            return self

        if instance is None:
            bound = copy.copy(self)
            bound.__self__ = owner
            return bound

        if self.__name__ not in instance.__dict__:
            if self.__func__ is not None:
                return self.__func__.__get__(instance, owner)
            return None

        return instance.__dict__[self.__name__]

    def __set__(self, instance, value):
        instance.__dict__[self.__name__] = value

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

    def copy(self, *args, **kwargs):
        # Non-call decorator form
        if len(args) == 1 and callable(args[0]) and not kwargs:
            func, *args = args
        else:
            func = None

        args = (*self._args, *args)
        kwargs = {**self._kwargs, **kwargs}
        obj = type(self)(*args, **kwargs)
        obj.__func__ = None

        if func:
            obj.wrap(func)

        return obj


class Argument(_MethodDecorator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = None

    def wrap(self, wrapped):
        if isinstance(wrapped, Argument):
            group = Group()

            self.wrap(wrapped.__func__)
            group.wrap(wrapped.__func__)
            group.add(wrapped)
            group.add(self)

            # Don't duplicate help message
            wrapped.__doc__ = None
            self.__doc__ = None

            return group

        if isinstance(wrapped, Group):
            group = wrapped

            self.wrap(group.__func__)
            group.add(self)

            # Don't duplicate help message
            self.__doc__ = None

            return group

        return super().wrap(wrapped)

    def copy(self, *args, **kwargs):
        arg = super().copy(*args, **kwargs)
        arg.group = self.group

        return arg

    def __get__(self, instance, owner):
        arg = super().__get__(instance, owner)

        if isinstance(arg, inspect.BoundArguments):
            inputs = instance.__dict__.pop(self.__name__)
            func = super().__get__(instance, owner)
            instance.__dict__[self.__name__] = inputs

            if callable(func):
                try:
                    outputs = func(*inputs.args, **inputs.kwargs)
                except AttributeError as err:
                    raise RuntimeError(
                        "Argument method raised AttributeError"
                    ) from err

                if inspect.isgenerator(outputs):
                    try:
                        while True:
                            instance.__dict__[self.__name__] = next(outputs)
                    except StopIteration as err:
                        outputs = err.value

                instance.__dict__[self.__name__] = outputs
                return outputs

            return inputs

        return arg

    @property
    def __auto_kwargs(self):
        kwargs = {}

        if self.__func__ is not None:
            # Bind to anything to skip the "self" argument
            func = self.__func__.__get__(object(), object)

            act_kwargs, f_kwargs = filter_action_kwargs(
                self._kwargs,
                action=FunctionBindAction,
            )

            if f_kwargs:
                act_kwargs.setdefault("kwargs", {})
                act_kwargs["kwargs"].update(f_kwargs)
            f_args = act_kwargs.get("args", ())
            f_kwargs = act_kwargs.get("kwargs", {})

            partial = functools.partial(func, *f_args, **f_kwargs)
            sig = inspect.signature(partial, follow_wrapped=False)
            params = sig.parameters

            kwargs["action"] = FunctionBindAction
            kwargs["func"] = func

        else:
            params = {}

        nargs_min = 0
        nargs_max = 0
        var_args = None
        var_kwargs = None
        first_arg = next(iter(params.keys())).upper() if params else None

        for name, param in params.items():
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                var_args = param
                continue

            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                var_kwargs = param
                continue

            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                # partial() objs accept kwargs that're already bound
                if name in f_kwargs:
                    continue

            if param.default == inspect.Parameter.empty:
                nargs_min += 1
                nargs_max += 1

            else:
                nargs_max += 1

        option_strings = self._args
        kwargs["dest"] = self.__name__

        doc = inspect.getdoc(self)
        if doc is not None:
            kwargs["help"] = doc.split("\n\n")[0]

        # attr = Argument()
        if self.__func__ is None and not option_strings:
            kwargs["nargs"] = 1

        # attr = Argument("--arg")
        elif self.__func__ is None:
            kwargs["nargs"] = "?"

        # func(a, *b)
        elif (var_args or var_kwargs) and nargs_min > 0:
            kwargs["nargs"] = "+"
            kwargs["metavar"] = (var_args or var_kwargs).name

        # func(*a)
        elif (var_args or var_kwargs) and nargs_min == 0:
            kwargs["nargs"] = "*"
            kwargs["metavar"] = (var_args or var_kwargs).name

        # func()
        elif (nargs_min, nargs_max) == (0, 0):
            kwargs["nargs"] = 0

        # func(a=None)
        elif (nargs_min, nargs_max) == (0, 1):
            kwargs["nargs"] = "?"
            kwargs["metavar"] = first_arg

        # func(a=None, b=None)
        elif nargs_min == 0:
            kwargs["nargs"] = "*"
            kwargs["metavar"] = first_arg

        # func(a, b=None)
        elif nargs_min != nargs_max:
            kwargs["nargs"] = "+"
            kwargs["metavar"] = first_arg

        # func(a, b)
        else:
            kwargs["nargs"] = nargs_min

            if option_strings:
                kwargs["metavar"] = tuple(params.keys())
            else:
                kwargs["metavar"] = first_arg

        def format_metavar(s):
            return s.replace("-","_").strip(" -_").upper()

        if "metavar" in kwargs:
            metavar = kwargs["metavar"]
            if isinstance(metavar, tuple):
                metavar = tuple(format_metavar(m) for m in metavar)
            else:
                metavar = format_metavar(metavar)
            kwargs["metavar"] = metavar

        return kwargs

    @property
    def __kwargs(self):
        kwargs = self.__auto_kwargs
        kwargs.update(self._kwargs)

        act_kwargs, f_kwargs = filter_action_kwargs(kwargs)

        act = act_kwargs.get("action", None)
        if isinstance(act, type) and issubclass(act, FunctionBindAction):
            if act_kwargs.get("count", False):
                act_kwargs["nargs"] = 0

            if f_kwargs:
                act_kwargs.setdefault("kwargs", {})
                act_kwargs["kwargs"].update(f_kwargs)

        return act_kwargs

    def build(self, parent):
        option_strings = self._args
        kwargs = self.__kwargs

        return parent.add_argument(*option_strings, **kwargs)

    def __property_from_kwargs(name):
        @property
        def prop(self):
            try:
                return self.__kwargs[name]
            except KeyError:
                raise AttributeError(
                    "Argument '{}' does not pass '{}' to add_argument"
                    .format(self.__name__, name)
                ) from None

        @prop.setter
        def prop(self, value):
            self._kwargs[name] = value

        @prop.deleter
        def prop(self):
            del self._kwargs[name]

        return prop

    @property
    def name_or_flags(self):
        return self._args or (self.__name__,)

    action = __property_from_kwargs("action")
    nargs = __property_from_kwargs("nargs")
    default = __property_from_kwargs("default")
    type = __property_from_kwargs("type")
    choices = __property_from_kwargs("choices")
    required = __property_from_kwargs("required")
    help = __property_from_kwargs("help")
    metavar = __property_from_kwargs("metavar")
    dest = __property_from_kwargs("dest")
    append = __property_from_kwargs("append")
    count = __property_from_kwargs("count")
    version = __property_from_kwargs("version")
    del __property_from_kwargs


class Group(_MethodDecorator):
    def __init__(self, *args, **kwargs):
        self._arguments = []
        self.group = None
        super().__init__(*args, **kwargs)

    def wrap(self, wrapped):
        if isinstance(wrapped, Argument):
            self.wrap(wrapped.__func__)
            self.add(wrapped)

            # Don't duplicate help message
            wrapped.__doc__ = None

            return self

        if isinstance(wrapped, Group):
            old_doc = self.__doc__
            self.wrap(wrapped.__func__)
            self.add(wrapped)

            # Don't override help message
            if old_doc is not None:
                wrapped.__doc__ = self.__doc__
                self.__doc__ = old_doc

            return self

        return super().wrap(wrapped)

    def copy(self, *args, **kwargs):
        grp = super().copy(*args, **kwargs)

        for arg in self._arguments:
            grp.add(arg)

        return grp

    def __get__(self, instance, owner):
        grp = super().__get__(instance, owner)

        if isinstance(grp, inspect.BoundArguments):
            inputs = instance.__dict__.pop(self.__name__)
            func = super().__get__(instance, owner)
            instance.__dict__[self.__name__] = inputs

            if callable(func):
                try:
                    outputs = func(*inputs.args, **inputs.kwargs)
                except AttributeError as err:
                    raise RuntimeError(
                        "Group method raised AttributeError"
                    ) from err

                if inspect.isgenerator(outputs):
                    try:
                        while True:
                            instance.__dict__[self.__name__] = next(outputs)
                    except StopIteration as err:
                        outputs = err.value

                instance.__dict__[self.__name__] = outputs
                return outputs

            return inputs

        return grp

    @property
    def __auto_kwargs(self):
        kwargs = {}

        doc = inspect.getdoc(self)
        if doc:
            blocks = doc.split("\n\n")
            kwargs["title"] = blocks[0].replace("\n", " ")
            if len(blocks) > 1:
                kwargs["description"] = "\n\n".join(blocks[1:])
        else:
            kwargs["title"] = self.__name__

        return kwargs

    @property
    def __kwargs(self):
        kwargs = self.__auto_kwargs
        kwargs.update(self._kwargs)

        return kwargs

    def build(self, parent):
        parser = parent.add_argument_group(*self._args, **self.__kwargs)

        items = list(self._arguments)
        while items:
            item = items.pop(0)
            item.__get__(self.__self__, type(self.__self__))

            # Argparse doesn't print help message for nested groups,
            # so we flatten them here.
            if isinstance(item, Group):
                items = list(item._arguments) + items
                continue

            item.build(parser)

        return parser

    def add(self, arg):
        self._arguments.append(arg)
        arg.group = self
        return arg

    def __property_from_kwargs(name):
        @property
        def prop(self):
            try:
                return self.__kwargs[name]
            except KeyError:
                raise AttributeError(
                    "Group '{}' does not pass '{}' to add_argument_group"
                    .format(self.__name__, name)
                ) from None

        @prop.setter
        def prop(self, value):
            self._kwargs[name] = value

        @prop.deleter
        def prop(self):
            del self._kwargs[name]

        return prop

    title = __property_from_kwargs("title")
    description = __property_from_kwargs("description")
    del __property_from_kwargs


class Subparsers(_MethodDecorator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commands = []

    def wrap(self, func):
        if isinstance(func, CommandMeta):
            self.add(func)
            return self

        return super().wrap(func)

    @property
    def __auto_kwargs(self):
        kwargs = {}

        doc = inspect.getdoc(self)
        if doc:
            blocks = doc.split("\n\n")
            kwargs["title"] = blocks[0].replace("\n", " ")
            kwargs["description"] = "\n\n".join(blocks[1:])
        else:
            kwargs["title"] = self.__name__

        kwargs["dest"] = self.__name__

        return kwargs

    @property
    def __kwargs(self):
        kwargs = self.__auto_kwargs
        kwargs.update(self._kwargs)

        return kwargs

    def build(self, parent):
        subparsers = parent.add_subparsers(*self._args, **self.__kwargs)

        for cmd in self._commands:
            cmd.build(subparsers)

        return subparsers

    def add(self, cmd):
        self._commands.append(cmd)
        return cmd

    def __property_from_kwargs(name):
        @property
        def prop(self):
            try:
                return self.__kwargs[name]
            except KeyError:
                raise AttributeError(
                    "Subparsers '{}' does not pass '{}' to add_subparsers"
                    .format(self.__name__, name)
                ) from None

        @prop.setter
        def prop(self, value):
            self._kwargs[name] = value

        @prop.deleter
        def prop(self):
            del self._kwargs[name]

        return prop

    title = __property_from_kwargs("title")
    description = __property_from_kwargs("description")
    dest = __property_from_kwargs("dest")
    del __property_from_kwargs


def command_call(call):
    def __call__(self, **kwargs):
        for kwarg, value in kwargs.items():
            func = getattr(self, kwarg)
            if not callable(func):
                setattr(self, kwarg, value)
                continue

            if isinstance(value, inspect.BoundArguments):
                setattr(self, kwarg, value)
                continue

            sig = inspect.signature(func)
            var_args = None
            var_kwargs = None

            for name, param in sig.parameters.items():
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    var_args = param

                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    var_kwargs = param
                    raise NotImplementedError

                elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                    raise NotImplementedError

            # func(*a)
            # func(a, *b)
            if var_args and isinstance(value, (list, set, tuple)):
                value = sig.bind(*value)

            # func()
            elif len(sig.parameters) == 0:
                value = sig.bind() if value else None

            # func(a)
            # func(a=None)
            elif len(sig.parameters) == 1:
                value = sig.bind(value)

            # func(a, b)
            # func(a, b=None)
            # func(a=None, b=None)
            else:
                value = sig.bind(*value)

            setattr(self, kwarg, value)

        for cmd in reversed(type(self).__mro__):
            if not isinstance(cmd, CommandMeta):
                continue

            for arg_name, arg in cmd.arguments():
                arg.__self__ = None
                try:
                    func = arg.__func__.__get__(object(), object)
                    sig = inspect.signature(func)
                    self.__dict__.setdefault(arg_name, sig.bind())
                except:
                    self.__dict__.setdefault(arg_name, None)

            for grp_name, grp in cmd.groups():
                grp.__self__ = None
                for arg in grp._arguments:
                    arg.__self__ = None
                    if not hasattr(arg, "dest") or arg.dest == argparse.SUPPRESS:
                        continue
                    try:
                        func = arg.__func__.__get__(object(), object)
                        sig = inspect.signature(func)
                        self.__dict__.setdefault(arg.dest, sig.bind())
                    except:
                        self.__dict__.setdefault(arg.dest, None)

                if grp_name not in (
                    arg.dest for arg in grp._arguments
                    if hasattr(arg, "dest")
                ):
                    try:
                        # grp.__get__(self, type(self)) would mutate self
                        func = grp.__func__.__get__(object(), object)
                        sig = inspect.signature(func)
                        self.__dict__.setdefault(grp_name, sig.bind())
                    except:
                        self.__dict__.setdefault(grp_name, None)

        for cmd in reversed(type(self).__mro__):
            if not isinstance(cmd, CommandMeta):
                continue

            for arg_name, arg in cmd.arguments():
                getattr(self, arg_name, None)

            for grp_name, grp in cmd.groups():
                getattr(self, grp_name, None)

        return call(self)

    functools.update_wrapper(__call__, call)
    return __call__


class CommandExit(Exception):
    def __init__(
        self,
        message=None,
        output=None,
        returncode=1,
        errno=None,
    ):
        if errno is not None:
            if message:
                errmsg = "[Errno {}] {}".format(errno, message)
            else:
                errmsg = "[Errno {}]".format(errno)
        else:
            errmsg = message

        self.returncode = returncode
        self.output = output
        self.message = message
        self.errno = errno
        super().__init__(errmsg)

    def __repr__(self):
        return "{}(output={!r}, returncode={!r}, message={!r})".format(
            type(self).__qualname__,
            self.output,
            self.returncode,
            self.message,
        )


class CommandMeta(type):
    def __new__(mcls, name, bases, attrs, **kwargs):
        call = attrs.get("__call__", None)

        if call is not None:
            attrs["__call__"] = command_call(call)

        cls = super().__new__(mcls, name, bases, attrs)
        cls.__custom_kwargs = kwargs
        return cls

    @property
    def __call__(cls):
        cls_call = cls.__dict__.get("__call__", None)
        cls_call = getattr(cls_call, "__func__", cls_call)

        if inspect.isgeneratorfunction(cls_call):
            return cls.__generator_call
        else:
            return cls.__normal_call

    def __normal_call(cls, *args, **kwargs):
        instance = super().__call__()
        raise_exit = kwargs.pop("__raise_CommandExit", False)

        if hasattr(instance, "__enter__"):
            with instance as inst:
                retval = inst(*args, **kwargs)
        else:
            retval = instance(*args, **kwargs)

        if isinstance(retval, CommandExit):
            if raise_exit:
                raise retval
            else:
                retval = retval.output

        return retval

    def __generator_call(cls, *args, **kwargs):
        instance = super().__call__()
        raise_exit = kwargs.pop("__raise_CommandExit", False)

        if hasattr(instance, "__enter__"):
            with instance as inst:
                retval = yield from inst(*args, **kwargs)
        else:
            retval = yield from instance(*args, **kwargs)

        if isinstance(retval, CommandExit):
            if raise_exit:
                raise retval
            else:
                retval = retval.output

        return retval

    def main(cls, *argv):
        if len(argv) == 0:
            prog, *argv = sys.argv

        parser = cls.parser
        args = parser.parse_args(argv)
        command = getattr(args, "__command")
        kwargs = {
            k: v for k, v in vars(args).items()
            if k != "__command"
        }

        root_logger = logging.getLogger()
        root_logger.addHandler(logging.StreamHandler())
        root_logger.setLevel(logging.NOTSET)

        if hasattr(command, "_logger"):
            logger = command._logger
        else:
            logging.getLogger(cls.__module__)

        def log_error(err):
            is_debug_level = logger.isEnabledFor(logging.DEBUG)
            if not is_debug_level and err.__cause__ is not None:
                log_error(err.__cause__)
            logger.error(err, exc_info=is_debug_level)

        try:
            output = command(__raise_CommandExit=True, **kwargs)

            if inspect.isgenerator(output):
                try:
                    while True:
                        print(next(output))
                except StopIteration as err:
                    output = err.value

            if output is not None:
                print(output)

        except CommandExit as exit:
            if exit.returncode != 0:
                log_error(exit)
            else:
                logger.warning(exit)

            if exit.output is not None:
                print(exit.output)

            sys.exit(exit.returncode)

        except Exception as err:
            log_error(err)
            sys.exit(1)

    def items(cls):
        def order(tup):
            attr, value = tup
            return (
                isinstance(value, Group),
                isinstance(value, Argument),
                isinstance(value, Subparsers),
                isinstance(value, CommandMeta),
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
            if isinstance(v, CommandMeta)
        )

    def subcommand(cls, arg):
        if isinstance(arg, CommandMeta):
            name = arg.__name__
            while hasattr(cls, name):
                name = "{}_".format(name)
            setattr(cls, name, arg)
            return arg

        def add_subcommand(cmd):
            name = arg.replace("-", "_")
            while hasattr(cls, name):
                name = "{}_".format(name)
            setattr(cls, name, cmd)
            cmd.__name__ = arg
            return cmd

        return add_subcommand

    @property
    def __auto_kwargs(cls):
        kwargs = {}

        doc = inspect.getdoc(cls)
        if doc is not None:
            blocks = doc.split("\n\n")

            for i, block in enumerate(blocks):
                if block.strip("- ") == "":
                    kwargs["help"] = blocks[0]
                    kwargs["description"] = "\n\n".join(blocks[:i])
                    kwargs["epilog"] = "\n\n".join(blocks[i+1:])
                    break
            else:
                kwargs["help"] = blocks[0]
                kwargs["description"] = doc

        kwargs["argument_default"] = argparse.SUPPRESS
        kwargs["formatter_class"] = argparse.RawDescriptionHelpFormatter
        kwargs["conflict_handler"] = "resolve"

        return kwargs

    @property
    def __kwargs(cls):
        kwargs = cls.__auto_kwargs
        kwargs.update(cls.__custom_kwargs)

        return kwargs

    @property
    def parser(cls):
        return cls.__build()

    def __build(cls, parent=None):
        kwargs = cls.__kwargs

        if parent is None:
            kwargs.pop("help", None)
            parser = argparse.ArgumentParser(**kwargs)

        else:
            parser = parent.add_parser(cls.__name__, **kwargs)

        subparsers = None

        for attr, value in cls.items():
            if isinstance(value, Group):
                group = getattr(cls, attr)
                if group.group is None:
                    group.build(parser)

            elif isinstance(value, Argument):
                arg = getattr(cls, attr)
                if arg.group is None:
                    arg.build(parser)

            elif isinstance(value, Subparsers):
                obj = getattr(cls, attr)
                subparsers = obj.build(parser)

            elif isinstance(value, CommandMeta):
                cmd = getattr(cls, attr)
                cmd.__self__ = cls

                if subparsers is None:
                    subparsers = parser.add_subparsers()
                cmd.__build(subparsers)

        parser.set_defaults(__command=cls)

        return parser

    build = __build

    def __property_from_kwargs(name):
        @property
        def prop(cls):
            if name in cls.__dict__:
                return cls.__dict__[name]

            try:
                return cls.__kwargs[name]
            except KeyError:
                raise AttributeError(
                    "Command '{}' does not pass '{}' to ArgumentParser"
                    .format(cls.__name__, name)
                ) from None

        @prop.setter
        def prop(cls, value):
            if name in cls.__dict__:
                prop = getattr(type(cls), name)
                delattr(type(cls), name)
                super().__setattr__(name, value)
                setattr(type(cls), name, prop)
            else:
                cls.__custom_kwargs[name] = value

        @prop.deleter
        def prop(cls):
            if name in cls.__dict__:
                prop = getattr(type(cls), name)
                delattr(type(cls), name)
                super().__delattr__(name)
                setattr(type(cls), name, prop)
            else:
                del cls.__custom_kwargs[name]

        return prop

    prog = __property_from_kwargs("prog")
    usage = __property_from_kwargs("usage")
    description = __property_from_kwargs("description")
    epilog = __property_from_kwargs("epilog")
    parents = __property_from_kwargs("parents")
    formatter_class = __property_from_kwargs("formatter_class")
    prefix_chars = __property_from_kwargs("prefix_chars")
    fromfile_prefix_chars = __property_from_kwargs("fromfile_prefix_chars")
    argument_default = __property_from_kwargs("argument_default")
    conflict_handler = __property_from_kwargs("conflict_handler")
    add_help = __property_from_kwargs("add_help")
    allow_abbrev = __property_from_kwargs("allow_abbrev")
    help = __property_from_kwargs("help")
    del __property_from_kwargs


class Command(metaclass=CommandMeta):
    def __init__(self):
        self.exitstack = contextlib.ExitStack()

    def __enter__(self):
        self.exitstack.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self.exitstack.__exit__(exc_type, exc_value, traceback)
