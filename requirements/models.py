from __future__ import unicode_literals

from django.db import models
from django import forms
from .reqlist import JSONConstants, RequirementsStatement, undecorated_component, unwrapped_component, SyntaxConstants

# Create your models here.
class RequirementsList(RequirementsStatement):
    """Describes a requirements list document (for example, major3, minorWGS).
    The requirements list document has a variety of titles of different lengths,
    as well as raw string contents in the requirements list format. It can also
    parse the raw contents and store its requirements statements as
    RequirementsStatement objects."""

    list_id = models.CharField(max_length=25)
    short_title = models.CharField(max_length=50, default="")
    medium_title = models.CharField(max_length=100, default="")
    title_no_degree = models.CharField(max_length=250, default="")
    #title = models.CharField(max_length=250, default="")

    contents = models.CharField(max_length=10000, default="")
    catalog_url = models.CharField(max_length=150, default="")

    #description = models.TextField(null=True)

    def __str__(self):
        return self.short_title + " - " + self.title

    def to_json_object(self, full=True, child_fn=None):
        """Encodes this requirements list into a dictionary that can be sent
        as JSON. If full is False, only returns the metadata about the requirements
        list. See the documentation of RequirementsStatement.to_json_object() for
        info about child_fn."""
        base = {
            JSONConstants.list_id: self.list_id,
            JSONConstants.short_title: self.short_title,
            JSONConstants.medium_title: self.medium_title,
            JSONConstants.title: self.title
        }
        if full:
            if self.requirements.exists():
                print(self.requirements.all())
                base[JSONConstants.requirements] = [child_fn(r) if child_fn is not None else r.to_json_object() for r in self.requirements.all()]
            base[JSONConstants.title_no_degree] = self.title_no_degree
            base[JSONConstants.description] = self.description if self.description is not None else ""

        return base

    def parse(self, contents_str, full=True):
        """Parses the given contents string, using only the header if full is
        False, or otherwise the entire requirements file. The RequirementsList
        must be created using the RequirementsList.objects.create() method or
        have already been saved prior to calling this method."""

        lines = contents_str.split('\n')
        # Remove full-line comments and strip newlines
        lines = [l.strip() for l in lines if l.find(SyntaxConstants.comment_character) != 0]
        # Remove partial-line comments
        lines = [l[:l.find(SyntaxConstants.comment_character)] if SyntaxConstants.comment_character in l else l for l in lines]

        # First line is the header
        first = lines.pop(0)
        header_comps = first.split('#,#')
        if len(header_comps):
            self.short_title = header_comps.pop(0)
        if len(header_comps):
            self.medium_title = header_comps.pop(0)
        if len(header_comps) > 1:
            self.title_no_degree = header_comps.pop(0)
            self.title = header_comps.pop(0)
        elif len(header_comps) > 0:
            self.title = header_comps.pop(0)

        while len(header_comps) > 0:
            comp = header_comps.pop(0)
            if "=" in comp:
                arg_comps = comp.split("=")
                if len(arg_comps) != 2:
                    print("{}: Unexpected number of = symbols in first line argument".format(self.list_id))
                    continue


        self.contents = contents_str

        if not full:
            return

        # Second line is the description of the course
        desc_line = lines.pop(0)
        if len(desc_line) > 0:
            self.description = desc_line.replace("\\n", "\n")

        self.save()
        if len(lines) == 0:
            print("{}: Reached end of file early!".format(self.list_id))
            return
        if len(lines[0]) != 0:
            print("{}: Third line isn't empty (contains \"{}\")".format(self.list_id, lines[0]))
            return

        lines.pop(0)

        # Parse top-level list
        top_level_sections = []
        while len(lines) > 0 and len(lines[0]) > 0:
            if lines.count <= 2:
                print("{}: Not enough lines for top-level sections - need variable names and descriptions on two separate lines.".format(self.list_id))
                return

            var_name = undecorated_component(lines.pop(0))
            description = undecorated_component(lines.pop(0).replace("\\n", "\n"))

            if SyntaxConstants.declaration_character in var_name or SyntaxConstants.declaration_character in description:
                print("{}: Encountered ':=' symbol in top-level section. Maybe you forgot the required empty line after the last section's description line?".format(self.list_id))
            top_level_sections.append((var_name, description))

        if len(lines) == 0:
            return
        lines.pop(0)

        # Parse variable declarations
        variables = {}
        while len(lines) > 0:
            current_line = lines.pop(0)
            if len(current_line) == 0:
                continue
            if SyntaxConstants.declaration_character not in current_line:
                print("{}: Unexpected line: {}".format(self.list_id, current_line))
                continue
            comps = current_line.split(SyntaxConstants.declaration_character)
            if len(comps) != 2:
                print("{}: Can't have more than one occurrence of \"{}\" on a line".format(self.list_id, SyntaxConstants.declaration_character))
                continue

            declaration = comps[0]
            statement_title = ""
            if SyntaxConstants.variable_declaration_separator in declaration:

                index = declaration.find(SyntaxConstants.variable_declaration_separator)
                variable_name = undecorated_component(declaration[:index])
                statement_title = undecorated_component(declaration[index + len(SyntaxConstants.variable_declaration_separator):])
            else:
                variable_name = undecorated_component(comps[0])

            statement = RequirementsStatement.initialize(statement_title, comps[1])
            variables[variable_name] = statement

        for name, description in top_level_sections:
            if name not in variables:
                print("{}: Undefined variable: {}".format(self.list_id, name))
                return

            req = variables[name]
            req.description = description
            req.list = self
            req.parent = self
            req.substitute_variables(variables)


class EditForm(forms.Form):
    email_address = forms.CharField(label='Email address', max_length=100, widget=forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Email address'}))
    reason = forms.CharField(label='Reason for submission', max_length=2000, widget=forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Reason for submission...'}))
    contents = forms.CharField(label='contents', max_length=10000, widget=forms.HiddenInput(), required=False)

class EditRequest(models.Model):
    type = models.CharField(max_length=10)
    email_address = models.CharField(max_length=100)
    reason = models.CharField(max_length=2000)
    contents = models.CharField(max_length=10000)
    timestamp = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return "{}{} request by {} at {}: {}".format("(Resolved) " if self.resolved else "", self.type, self.email_address, self.timestamp, self.reason)
